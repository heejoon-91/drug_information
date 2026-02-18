from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('drugs', '0007_remove_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='DrugPermitInfo',
            fields=[
                ('item_seq', models.CharField(max_length=50, primary_key=True, serialize=False, verbose_name='품목기준코드')),
                ('item_name', models.TextField(verbose_name='제품명')),
                ('item_eng_name', models.TextField(blank=True, null=True, verbose_name='제품명(영문)')),
                ('entp_name', models.CharField(blank=True, max_length=255, null=True, verbose_name='업체명')),
                ('main_ingr_name', models.TextField(blank=True, null=True, verbose_name='주성분')),
                ('etc_otcc_name', models.CharField(blank=True, max_length=50, null=True, verbose_name='전문/일반')),
                ('permit_date', models.DateField(blank=True, null=True, verbose_name='허가일자')),
                ('valid_term', models.TextField(blank=True, null=True, verbose_name='유효기한')),
            ],
            options={
                'verbose_name': '의약품 허가 정보',
                'verbose_name_plural': '의약품 허가 정보 목록',
                'db_table': 'drug_permit_info',
                'managed': True,
            },
        ),
    ]
