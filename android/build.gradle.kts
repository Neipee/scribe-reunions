// Versions éprouvées ensemble (AGP 8.7 + Gradle 8.11 + Kotlin 2.0), choisies pour la fiabilité
// de la compilation dans GitHub Actions plutôt que pour la nouveauté.
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
}
