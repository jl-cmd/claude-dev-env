# Django Patterns Reference

> Load this file when working with Django models, views, templates, or migrations.

## Model Patterns

**NEVER:**

- **Create separate user models** - Extend Django's User with OneToOneField
  - Example: `UserProfile(user=OneToOneField(User, related_name='profile'))`
  - See: https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#extending-the-existing-user-model

- **Use confusing model/field names** - Match semantics & avoid conflicts
  - "Settings" = user preferences (preferences, settings, display options), "UserProfile" = user metadata
  - `custom_name` avoids conflict with User.username

- **Break model fields across multiple lines** - Match the style of other fields in the model
  - Bad: Multi-line ForeignKey definition
  - Good: `evolves_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='evolutions')`
  - Consistency within the model class matters more than arbitrary line length rules

- **Circumvent Django ORM for database operations** - Always use Django models for DB access
  - Django ORM handles migrations, relationships, and abstractions under the hood
  - Bypassing it creates inconsistencies with migrations and model state
  - For DB operations: Use Django models, views, management commands
  - For non-DB tools: Use pure Python scripts (file processing, API calls, asset uploads)

## Template Patterns

**NEVER:**

- **Put view-specific template code in base.html** - Only in the template that uses it
  - Example: `{% if layout %}` in base.html when only home view defines layout
  - If variable is always present in specific template, no conditional needed

## Production Migrations (Post-Launch ONLY)

**CRITICAL:** After launch, model changes MUST be backwards-compatible.

**Why:** Manual migration takes 2+ minutes. New code runs against old schema during this window.

### Safe vs Unsafe Changes

| Safe | Unsafe |
|------|--------|
| Nullable fields | Removing fields |
| Fields with defaults | Renaming fields |
| New models | Non-null without defaults |
| | Type changes |

### Migration Strategy

1. Deploy code working with both schemas
2. Run migration (2+ min)
3. Verify production
4. Deploy cleanup if needed

*During development: manual migration is fine, no big deal.*

## API Contract Changes (Post-Launch)

**CRITICAL:** After launch, API contract changes MUST be backwards-compatible.

**Why:** Users may have old client code cached. Old clients must work with new API.

### Safe vs Unsafe Changes

| Safe | Unsafe |
|------|--------|
| New optional fields | Removing fields |
| New endpoints | Renaming fields |
| Additive changes | Changing field types |
| | Removing endpoints |

### API Evolution Strategy

1. Add new fields/endpoints alongside old ones
2. Deploy frontend that handles both old and new
3. Deprecate old fields (but keep working)
4. Remove old fields only after all clients updated
