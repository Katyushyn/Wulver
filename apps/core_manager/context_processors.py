from apps.core_manager.services.reviews import get_reviews


def external_reviews(request):
    reviews = get_reviews()

    return {
        "external_reviews": reviews,
        "reviews": reviews,
    }
