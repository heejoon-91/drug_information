from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("smart-search/", views.smart_search, name="smart_search"),
    path("smart-search-products/", views.symptom_products_page, name="symptom_products_page"),
    path("manual-check/", views.symptom_products_page, name="manual_check"),
    path("api/search/", views.smart_search_api, name="smart_search_api"),
    path("api/manual-check/", views.symptom_products_api, name="manual_check_api"),
    path("api/pharmacies/", views.pharmacy_api, name="pharmacy_api"),
    path("api/symptom-products/", views.symptom_products_api, name="symptom_products_api"),
    path("api/label-image/", views.label_image_api, name="label_image_api"),
]
