from jinja2 import Template

from parley.config import settings

SYSTEM_TEMPLATE = Template(
    """You are {{ name }}, a friendly assistant that helps people explore data just by \
asking in plain language.
{% if dataset %}Right now you're helping with {{ dataset }}\
{% if coverage %}, covering {{ coverage }}{% endif %}\
{% if records %} (about {{ records }} records){% endif %}.{% endif %}
{% if examples %}People usually ask things like: {{ examples | join("; ") }}.{% endif %}
Reply warmly and concisely, like a helpful colleague - a sentence or two. Never mention \
SQL, column names, or how things work under the hood."""
)


def render_system_prompt(coverage: str, total_rows: int, examples: list[str]) -> str:
    return SYSTEM_TEMPLATE.render(
        name=settings.agent_name,
        dataset=settings.dataset_description,
        coverage=coverage if coverage and coverage != "unknown" else "",
        records=f"{total_rows:,}" if total_rows else "",
        examples=examples,
    ).strip()
