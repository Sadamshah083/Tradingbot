from django.db import migrations


def backfill(apps, schema_editor):
    """People who already paid are customers, not new leads."""
    Profile = apps.get_model("accounts", "Profile")
    Order = apps.get_model("orders", "Order")
    paid_users = set(Order.objects.filter(status="paid").values_list("user_id", flat=True))
    for p in Profile.objects.all():
        if p.lead_status == "new" and (p.purchased > 0 or p.bot_access or p.user_id in paid_users):
            p.lead_status = "customer"
            p.save(update_fields=["lead_status"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_profile_lead_note_profile_lead_status"), ("orders", "0002_order_receipt_url_order_stripe_payment_intent_and_more")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
