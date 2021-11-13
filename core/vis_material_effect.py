class VisMaterialEffect:
    library: str
    name: str
    param: str

    def __init__(self, library: str, name: str, param: str) -> None:
        self.library = library
        self.name = name
        self.param = param
