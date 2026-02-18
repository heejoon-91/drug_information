from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('drugs', '0006_userprofile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='eyakinfo',
            name='ee_doc_url',
        ),
        migrations.RemoveField(
            model_name='eyakinfo',
            name='nb_doc_url',
        ),
        migrations.RemoveField(
            model_name='eyakinfo',
            name='ud_doc_url',
        ),
    ]
