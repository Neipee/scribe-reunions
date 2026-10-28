import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Version fournie par le workflow (tag v0.1.0 -> 0.1.0, numéro d'exécution -> versionCode).
val scribeVersionName = (findProperty("scribeVersionName") as String?) ?: "0.0.0-dev"
val scribeVersionCode = (findProperty("scribeVersionCode") as String?)?.toInt() ?: 1

// Clé de signature : fournie par le workflow via des variables d'environnement, jamais dans le dépôt.
val keystorePath: String? = System.getenv("SCRIBE_KEYSTORE")

android {
    namespace = "com.neipee.scribe"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.neipee.scribe"
        minSdk = 26
        targetSdk = 35
        versionCode = scribeVersionCode
        versionName = scribeVersionName
    }

    signingConfigs {
        create("release") {
            if (keystorePath != null) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("SCRIBE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("SCRIBE_KEY_ALIAS")
                keyPassword = System.getenv("SCRIBE_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (keystorePath != null) signingConfigs.getByName("release") else null
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = false
    }

    // Pas de bloc de métadonnées de dépendances (chiffré pour Google Play) dans l'APK.
    dependenciesInfo {
        includeInApk = false
        includeInBundle = false
    }

    lint {
        abortOnError = false
        textReport = true
        textOutput = file("stdout")
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

// Aucune dépendance : uniquement le framework Android et la bibliothèque standard Kotlin.
