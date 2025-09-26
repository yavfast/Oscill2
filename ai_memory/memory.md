# Project Memory

## Build System Upgrade (2025-09-26)
- Upgraded Gradle Wrapper to **8.5** (stable) (distributionUrl already pointed to 8.5).
- Selected **Android Gradle Plugin 8.3.2** because AGP 8.5.x requires Gradle >= 8.7. Requirement from user was only to move Gradle to 8.5, so AGP pinned to highest compatible.
- Added **namespace** to `app` and `mpchart` modules.
- Increased **compileSdkVersion / targetSdkVersion** to 34 (modern, required for Play compliance and AGP 8.x tooling benefits).
- Raised **minSdkVersion** from 15 -> 19 (AGP 8.x minimum is 19).
- Set **Java toolchain / runtime** to Java 17 via `org.gradle.java.home` in `gradle.properties`.
- Removed deprecated **package** attribute from `AndroidManifest.xml` in both app and library; rely on Gradle namespace.
- Removed legacy `sourcesJar`, `javadoc`, `javadocJar` tasks in MPAndroidChart module (incompatible classifier usage under Gradle 8).
- Fixed manifest for `MainActivity` adding `android:exported="true"` (required with intent-filter and targetSdk >= 31).
- Updated **JUnit** to 4.13.2 across modules.
- Build now succeeds: `assembleDebug` passes with only deprecation/unchecked warnings.

## Potential Next Improvements
- Update dependencies: appcompat (>=1.7.0), constraintlayout (>=2.1.4), gson (consider 2.10.1).
- Add Java toolchain block instead of org.gradle.java.home for portability.
- Enable `lint` and address deprecation warnings.
- Consider migrating to Kotlin DSL (`build.gradle.kts`) later.
- Consider enabling R8 minification for release.

## Rationale Notes
- Chose not to move Gradle beyond 8.5 because user explicitly requested 8.5.
- Not upgrading AGP beyond 8.3.2 to avoid forced wrapper bump to 8.7+.

## Current Verified State
- Command `./gradlew clean assembleDebug` (with Java 17) succeeds.
