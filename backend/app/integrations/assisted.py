"""User-supplied job content only. These adapters never access a portal or a browser session."""

from app.integrations.base import JobSourceAdapter, SourceCapabilities, SourceCapabilityError
from app.schemas import JobData


class AssistedSourceAdapter(JobSourceAdapter):
    capabilities = SourceCapabilities(search=False, prepare=True, submit=False)

    def search(self, query: str = "", board: str | None = None) -> list[JobData]:
        raise SourceCapabilityError("Usa la importación asistida: pega el texto y el enlace de la oferta.")


class LinkedInAssistedAdapter(AssistedSourceAdapter):
    name = "linkedin"
    label = "LinkedIn · Importación asistida"
    description = "Contenido pegado por el usuario. Inicio de sesión y postulación desde su propio navegador."


class ComputrabajoAssistedAdapter(AssistedSourceAdapter):
    name = "computrabajo"
    label = "Computrabajo · Importación asistida"
    description = (
        "Contenido pegado por el usuario. Sin lectura automática del portal ni acceso a credenciales."
    )


class ManualSourceAdapter(AssistedSourceAdapter):
    name = "manual"
    label = "Otro portal · Importación asistida"
    description = "Oferta aportada por el usuario con su texto y enlace original; envío manual."
