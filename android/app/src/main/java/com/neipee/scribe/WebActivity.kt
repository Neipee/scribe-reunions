package com.neipee.scribe

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.view.WindowManager
import android.webkit.PermissionRequest
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import java.io.ByteArrayInputStream

/**
 * Interface du PoC (servie par le PC) en plein écran.
 *
 * - Seule l'origine du PC configuré est chargée ; toute autre requête est bloquée.
 * - Le certificat auto-signé n'est accepté que s'il a l'empreinte vérifiée par l'utilisateur.
 * - Le micro n'est accordé qu'à cette origine, après la permission Android RECORD_AUDIO.
 * - Le sélecteur de fichiers Android sert les <input type="file"> de la page (import audio).
 * - L'écran reste allumé tant que cet écran est affiché (donc pendant l'enregistrement).
 */
class WebActivity : Activity() {

    companion object {
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"
        const val EXTRA_TOKEN = "token"
        const val EXTRA_PIN = "pin"
        private const val REQUEST_MIC = 1
        private const val REQUEST_FILE = 2

        /** Erreurs de certificat tolérées quand l'empreinte correspond exactement à celle épinglée. */
        private val PINNABLE_ERRORS = setOf(
            SslError.SSL_UNTRUSTED, SslError.SSL_IDMISMATCH, SslError.SSL_EXPIRED,
            SslError.SSL_NOTYETVALID, SslError.SSL_DATE_INVALID,
        )
    }

    private lateinit var address: ServerAddress
    private lateinit var pin: String
    private lateinit var webView: WebView
    private lateinit var errorPanel: View
    private lateinit var errorText: TextView
    private var pendingMicRequest: PermissionRequest? = null
    private var pendingFileCallback: ValueCallback<Array<Uri>>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val host = intent.getStringExtra(EXTRA_HOST)
        val token = intent.getStringExtra(EXTRA_TOKEN)
        val pinned = intent.getStringExtra(EXTRA_PIN)
        if (host == null || token == null || pinned == null) {
            finish()
            return
        }
        address = ServerAddress(host, intent.getIntExtra(EXTRA_PORT, ServerAddress.DEFAULT_PORT), token)
        pin = pinned

        // Enregistrement en arrière-plan hors périmètre : on garde au moins l'écran allumé.
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_web)
        SystemBars.pad(findViewById(R.id.root))
        webView = findViewById(R.id.web)
        errorPanel = findViewById(R.id.error_panel)
        errorText = findViewById(R.id.error_text)
        findViewById<Button>(R.id.retry).setOnClickListener { load() }
        findViewById<Button>(R.id.change_address).setOnClickListener { finish() }

        configureWebView()
        load()
    }

    override fun onDestroy() {
        pendingMicRequest?.deny()
        pendingMicRequest = null
        pendingFileCallback?.onReceiveValue(null)
        pendingFileCallback = null
        if (::webView.isInitialized) webView.destroy()
        super.onDestroy()
    }

    @SuppressLint("SetJavaScriptEnabled") // l'interface du PoC est en JavaScript ; seule l'origine du PC est chargée
    private fun configureWebView() {
        WebView.setWebContentsDebuggingEnabled(false)
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setGeolocationEnabled(false)
            setSupportMultipleWindows(false)
            javaScriptCanOpenWindowsAutomatically = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            safeBrowsingEnabled = false
        }
        webView.webViewClient = Client()
        webView.webChromeClient = Chrome()
    }

    private fun load() {
        errorPanel.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl(address.pageUrl)
    }

    private fun isAllowed(uri: Uri?): Boolean =
        uri != null && address.sameOrigin(uri.scheme, uri.host, uri.port)

    private fun showError(message: String) = runOnUiThread {
        if (isFinishing || isDestroyed) return@runOnUiThread
        errorText.text = message
        errorPanel.visibility = View.VISIBLE
        webView.visibility = View.INVISIBLE
    }

    private inner class Client : WebViewClient() {

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
            !isAllowed(request.url) // true = navigation bloquée

        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
            val scheme = request.url.scheme?.lowercase()
            if (scheme == "data" || scheme == "blob" || isAllowed(request.url)) return null
            // Toute autre destination est refusée : l'appli ne contacte que le PC configuré.
            return WebResourceResponse(
                "text/plain", "utf-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(ByteArray(0))
            )
        }

        // Pas d'acceptation aveugle : seulement l'hôte configuré ET l'empreinte vérifiée par l'utilisateur.
        @SuppressLint("WebViewClientOnReceivedSslError")
        override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
            val fingerprint = Tls.fingerprintOf(error.certificate)
            if (isAllowed(Uri.parse(error.url)) && fingerprint == pin && error.primaryError in PINNABLE_ERRORS) {
                handler.proceed()
                return
            }
            handler.cancel()
            showError(
                if (fingerprint != null && fingerprint != pin) {
                    "Le PC présente un certificat différent de celui que vous avez vérifié : connexion bloquée. " +
                        "Revenez à l'écran d'adresse et reconnectez-vous pour comparer la nouvelle empreinte."
                } else {
                    "Certificat du PC refusé (erreur ${error.primaryError}). Relancez le PC avec « python run.py --lan »."
                }
            )
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (!request.isForMainFrame) return
            showError(
                when (error.errorCode) {
                    WebViewClient.ERROR_HOST_LOOKUP, WebViewClient.ERROR_CONNECT, WebViewClient.ERROR_TIMEOUT ->
                        Tls.unreachable(address)
                    else -> "Erreur réseau : ${error.description}. ${Tls.unreachable(address)}"
                }
            )
        }

        override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, response: WebResourceResponse) {
            if (request.isForMainFrame && response.statusCode == 403) showError(Tls.TOKEN_REFUSED)
        }
    }

    private inner class Chrome : WebChromeClient() {

        override fun onPermissionRequest(request: PermissionRequest) {
            val audioOnly = request.resources.isNotEmpty() &&
                request.resources.all { it == PermissionRequest.RESOURCE_AUDIO_CAPTURE }
            if (!audioOnly || !isAllowed(request.origin)) {
                request.deny()
                return
            }
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
            } else {
                pendingMicRequest?.deny()
                pendingMicRequest = request
                requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_MIC)
            }
        }

        override fun onPermissionRequestCanceled(request: PermissionRequest) {
            if (pendingMicRequest == request) pendingMicRequest = null
        }

        /**
         * <input type="file"> de la page (import d'un fichier audio). On ouvre le sélecteur de
         * documents d'Android ; le fichier choisi est lu par la WebView et envoyé au seul PC.
         * Pas de filtre de type : certains formats audio ont un type MIME inconnu du téléphone,
         * la page vérifie elle-même l'extension.
         */
        override fun onShowFileChooser(
            view: WebView,
            filePathCallback: ValueCallback<Array<Uri>>,
            fileChooserParams: WebChromeClient.FileChooserParams,
        ): Boolean {
            pendingFileCallback?.onReceiveValue(null)
            pendingFileCallback = filePathCallback
            val intent = Intent(Intent.ACTION_GET_CONTENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*")
                .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, fileChooserParams.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE)
            try {
                startActivityForResult(intent, REQUEST_FILE)
            } catch (e: ActivityNotFoundException) {
                pendingFileCallback = null
                filePathCallback.onReceiveValue(null)
                Toast.makeText(this@WebActivity, "Aucune application ne permet de choisir un fichier sur ce téléphone.",
                    Toast.LENGTH_LONG).show()
            }
            return true
        }
    }

    @Deprecated("API Activity historique, suffisante ici (pas de dépendance AndroidX).")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_FILE) return
        val callback = pendingFileCallback ?: return
        pendingFileCallback = null
        // Toujours rappeler le callback (null si annulé), sinon la page ne peut plus rouvrir le sélecteur.
        callback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_MIC) return
        val request = pendingMicRequest ?: return
        pendingMicRequest = null
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
        } else {
            request.deny()
            explainMicDenied()
        }
    }

    private fun explainMicDenied() {
        if (shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO)) {
            Toast.makeText(this, "Micro refusé : sans cette autorisation, Scribe ne peut pas enregistrer.",
                Toast.LENGTH_LONG).show()
            return
        }
        // Refus définitif : Android ne redemandera plus, il faut passer par les paramètres.
        AlertDialog.Builder(this)
            .setTitle("Micro refusé")
            .setMessage("Scribe a besoin du micro pour enregistrer. Autorisez-le dans Paramètres > " +
                "Applications > Scribe > Autorisations > Micro, puis appuyez de nouveau sur Enregistrer.")
            .setPositiveButton("Ouvrir les paramètres") { _, _ ->
                startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.fromParts("package", packageName, null)))
            }
            .setNegativeButton("Plus tard", null)
            .show()
    }
}
