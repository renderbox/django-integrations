from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from integrations.encrypted_fields import EncryptedTextField
from integrations.fields.encrypted import EncryptedJSONField

ENCRYPTED_FIELD_TYPES = (EncryptedTextField, EncryptedJSONField)


def _iter_encrypted_field_models():
    """
    Walk every installed model (any app, not just this package's own
    Credential) for fields that are an EncryptedTextField or
    EncryptedJSONField.
    """
    for model in apps.get_models():
        field_names = [
            field.name
            for field in model._meta.get_fields()
            if isinstance(field, ENCRYPTED_FIELD_TYPES)
        ]
        if field_names:
            yield model, field_names


class Command(BaseCommand):
    help = (
        "Re-encrypt every EncryptedTextField/EncryptedJSONField value, across "
        "all installed apps, with the current primary ENCRYPTED_FIELD_KEYS key.\n"
        "\n"
        "Rotation workflow:\n"
        "  1. Add a new key to the front of ENCRYPTED_FIELD_KEYS - it becomes primary.\n"
        "  2. Keep the old key(s) in the list so existing data still decrypts.\n"
        "  3. Run this command to re-encrypt every stored value with the new key.\n"
        "  4. Each row is re-read and verified immediately after being rewritten.\n"
        "  5. Once satisfied, remove the retired key from ENCRYPTED_FIELD_KEYS."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which models/fields/rows would be re-encrypted without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total_rows = 0
        total_errors = 0

        for model, field_names in _iter_encrypted_field_models():
            manager = model._default_manager
            field_list = ", ".join(field_names)

            if dry_run:
                row_count = manager.count()
                self.stdout.write(
                    f"[dry-run] {model._meta.label}: would re-encrypt {row_count} "
                    f"row(s) across field(s) {field_list}"
                )
                total_rows += row_count
                continue

            updated = 0
            for obj in manager.all().iterator():
                values = {name: getattr(obj, name) for name in field_names}
                manager.filter(pk=obj.pk).update(**values)

                fresh = manager.get(pk=obj.pk)
                for name in field_names:
                    if getattr(fresh, name) != values[name]:
                        total_errors += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"{model._meta.label} pk={obj.pk!r} field {name!r}: "
                                "verification failed after re-encryption."
                            )
                        )
                updated += 1

            self.stdout.write(
                f"{model._meta.label}: re-encrypted {updated} row(s) across "
                f"field(s) {field_list}"
            )
            total_rows += updated

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"[dry-run] {total_rows} row(s) would be processed.")
            )
            return

        if total_errors:
            raise CommandError(
                f"{total_errors} verification failure(s) out of {total_rows} "
                "row(s) processed."
            )

        self.stdout.write(self.style.SUCCESS(f"Done. {total_rows} row(s) processed."))
