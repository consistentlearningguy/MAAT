"""Feature flag metadata used by backend and docs exports."""

FEATURE_FLAGS = {
    "enable_investigator_mode": {
        "default": False,
        "description": "Enables backend investigation routes and review workflows.",
    },
    "enable_clear_web_connectors": {
        "default": False,
        "description": "Enables optional public search/news/forum connectors.",
    },
    "enable_public_profile_checks": {
        "default": False,
        "description": "Enables username permutation and profile-existence checks.",
    },
    "enable_reverse_image_hooks": {
        "default": False,
        "description": "Enables reverse-image workflow hooks only.",
    },
    "enable_local_face_workflow": {
        "default": False,
        "description": "Enables local-only face workflows when optional deps are installed.",
    },
    "enable_dark_web_connectors": {
        "default": False,
        "description": "Enables lawful indexing/search connectors only; disabled by default.",
    },
    "enable_experimental_connectors": {
        "default": False,
        "description": "Allows unstable adapters such as OnionSearch scaffolds.",
    },
}
