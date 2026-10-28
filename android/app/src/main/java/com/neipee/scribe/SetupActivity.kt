package com.neipee.scribe

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** Écran de configuration : adresse du PC, jeton, vérification du certificat, puis ouverture. */
class SetupActivity : Activity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var addressField: EditText
    private lateinit var tokenField: EditText
    private lateinit var connectButton: Button
    private lateinit var progress: ProgressBar
    private lateinit var statusText: TextView
    private lateinit var statusColors: ColorStateList
    private lateinit var pinsText: TextView
    private val worker: ExecutorService = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)
        SystemBars.pad(findViewById(R.id.root))
        prefs = Prefs.of(this)

        addressField = findViewById(R.id.address)
        tokenField = findViewById(R.id.token)
        connectButton = findViewById(R.id.connect)
        progress = findViewById(R.id.progress)
        statusText = findViewById(R.id.status)
        statusColors = statusText.textColors
        pinsText = findViewById(R.id.pins)

        if (savedInstanceState == null) {
            addressField.setText(prefs.getString(Prefs.ADDRESS, ""))
            tokenField.setText(prefs.getString(Prefs.TOKEN, ""))
        }
        connectButton.setOnClickListener { connect() }
        tokenField.setOnEditorActionListener { _, actionId, _ ->
            val go = actionId == EditorInfo.IME_ACTION_GO
            if (go) connect()
            go
        }
        findViewById<Button>(R.id.forget).setOnClickListener { confirmForgetPins() }
        refreshPins()
    }

    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
    }

    private fun connect() {
        val address = try {
            ServerAddress.parse(addressField.text.toString(), tokenField.text.toString())
        } catch (e: AddressException) {
            showError(e.message ?: "Adresse invalide.")
            return
        }
        tokenField.setText(address.token)
        setBusy("Connexion au PC ${address.display}…")
        val pin = prefs.getString(Prefs.pinKey(address), null)
        if (pin == null) fetchAndConfirm(address, changed = false) else verify(address, pin)
    }

    /** Lit l'empreinte présentée par le PC et demande à l'utilisateur de la comparer. */
    private fun fetchAndConfirm(address: ServerAddress, changed: Boolean) {
        worker.execute {
            val result = runCatching { Tls.fetchFingerprint(address) }
            ui {
                result.fold(
                    onSuccess = { askTrust(address, it, changed) },
                    onFailure = { showError(Tls.describe(it, address)) },
                )
            }
        }
    }

    private fun verify(address: ServerAddress, pin: String) {
        worker.execute {
            val access = Tls.checkAccess(address, pin)
            ui {
                when (access) {
                    is Tls.Access.Ok -> open(address, pin)
                    is Tls.Access.CertChanged -> fetchAndConfirm(address, changed = true)
                    is Tls.Access.Failure -> showError(access.message)
                }
            }
        }
    }

    private fun askTrust(address: ServerAddress, fingerprint: String, changed: Boolean) {
        val intro = if (changed) {
            "Le PC ${address.display} présente un certificat différent de celui que vous aviez vérifié. " +
                "C'est normal s'il a été relancé avec --new-cert ou réinstallé. Sinon, quelqu'un " +
                "pourrait s'interposer : n'acceptez pas.\n\nNouvelle empreinte SHA-256 :"
        } else {
            "Comparez cette empreinte SHA-256 avec celle affichée dans la console du PC " +
                "(ligne « Empreinte SHA-256 du certificat »). Elles doivent être identiques :"
        }
        val pad = (20 * resources.displayMetrics.density).toInt()
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad / 2, pad, 0)
            addView(TextView(context).apply { text = intro })
            addView(TextView(context).apply {
                text = Tls.forDisplay(fingerprint)
                typeface = Typeface.MONOSPACE
                setTextIsSelectable(true)
                setPadding(0, pad / 2, 0, 0)
            })
        }
        AlertDialog.Builder(this)
            .setTitle(if (changed) "Certificat du PC changé" else "Vérifier le certificat du PC")
            .setView(content)
            .setCancelable(false)
            .setPositiveButton("Identiques, faire confiance") { _, _ ->
                prefs.edit().putString(Prefs.pinKey(address), fingerprint).apply()
                refreshPins()
                setBusy("Vérification du jeton…")
                verify(address, fingerprint)
            }
            .setNegativeButton("Annuler") { _, _ ->
                showError("Connexion annulée : certificat non confirmé.")
            }
            .show()
    }

    private fun open(address: ServerAddress, pin: String) {
        prefs.edit()
            .putString(Prefs.ADDRESS, addressField.text.toString().trim())
            .putString(Prefs.TOKEN, address.token)
            .apply()
        setIdle("")
        startActivity(
            Intent(this, WebActivity::class.java)
                .putExtra(WebActivity.EXTRA_HOST, address.host)
                .putExtra(WebActivity.EXTRA_PORT, address.port)
                .putExtra(WebActivity.EXTRA_TOKEN, address.token)
                .putExtra(WebActivity.EXTRA_PIN, pin)
        )
    }

    private fun confirmForgetPins() {
        AlertDialog.Builder(this)
            .setMessage("Oublier les certificats vérifiés ? Il faudra comparer de nouveau l'empreinte au prochain raccordement.")
            .setPositiveButton("Oublier") { _, _ ->
                Prefs.forgetPins(prefs)
                refreshPins()
            }
            .setNegativeButton("Annuler", null)
            .show()
    }

    private fun refreshPins() {
        val pins = Prefs.pins(prefs)
        pinsText.text = if (pins.isEmpty()) {
            "Aucun certificat vérifié pour l'instant."
        } else {
            "Certificats vérifiés :\n" + pins.joinToString("\n") { (server, fp) ->
                "$server : ${fp.take(11)}…${fp.takeLast(11)}"
            }
        }
    }

    private fun setBusy(message: String) {
        connectButton.isEnabled = false
        progress.visibility = View.VISIBLE
        statusText.setTextColor(statusColors)
        statusText.text = message
    }

    private fun setIdle(message: String) {
        connectButton.isEnabled = true
        progress.visibility = View.GONE
        statusText.setTextColor(statusColors)
        statusText.text = message
    }

    private fun showError(message: String) {
        setIdle(message)
        statusText.setTextColor(getColor(R.color.scribe_error))
    }

    private fun ui(block: () -> Unit) = runOnUiThread {
        if (!isFinishing && !isDestroyed) block()
    }
}
