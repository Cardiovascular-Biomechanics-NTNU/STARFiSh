"""Historical C++ comparison profile; never selected by production Starfish."""

from UtilityLib.netlistPyAdapter import NetlistPyAdapter


class LegacyPostFinalizeAdapter(NetlistPyAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, controller_phase="legacy_post_finalize", **kwargs)
