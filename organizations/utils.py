def get_organization_media_path_prefix(instance, filename):
    return f"organizations/{instance.slug}/{filename}"


def get_platform_media_path_prefix(instance, filename):
    return f"platforms/{instance.slug}/{filename}"


def get_organization_slug(instance):
    return f"{instance.name}-{str(instance.uid).split('-')[0]}"


def get_platform_slug(instance):
    return f"{instance.name}-{str(instance.uid).split('-')[0]}"
