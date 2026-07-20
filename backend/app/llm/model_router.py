from ..config import Settings


def model_route(settings: Settings, task: str) -> str:
    routes = {
        "compile": settings.qwen_compiler_model,
        "repair": settings.qwen_compiler_model,
        "adjudicate": settings.qwen_adjudicator_model,
        "explain": settings.qwen_explanation_model,
    }
    return routes[task]

