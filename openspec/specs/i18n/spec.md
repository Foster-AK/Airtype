## Requirements

### Requirement: Translation System

The system SHALL provide a `tr(key)` function that returns the translated string for the current language. If a translation is missing, the system SHALL fall back to zh-TW, and then fall back to the key itself.

#### Scenario: Existing translation key

- **WHEN** `tr("settings.general.title")` is called with the language set to "en"
- **THEN** the English translation string SHALL be returned

#### Scenario: Fallback when translation is missing

- **WHEN** `tr("some.key")` is called and the key does not exist in the current language
- **THEN** the system SHALL fall back and return the zh-TW translation as a fallback

---
### Requirement: JSON-Based Translation Files

Translations SHALL be stored as JSON translation files in the `locales/` directory: `zh_TW.json`, `zh_CN.json`, `en.json`, and `ja.json`.

#### Scenario: Loading translation files

- **WHEN** the language is set to "en"
- **THEN** the system SHALL load `locales/en.json` for translation lookups

---
### Requirement: Runtime Language Switching

The language SHALL be switchable at runtime without restarting the application. All UI components SHALL refresh their text when the language changes, via Signal-based language change notifications.

#### Scenario: Switching language at runtime

- **WHEN** the user switches the language from zh-TW to English in the settings
- **THEN** all UI labels SHALL immediately update to English without requiring a restart
