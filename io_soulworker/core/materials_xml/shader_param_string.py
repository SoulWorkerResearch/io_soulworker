class ShaderParamString(dict):
    """Parse a Vision ``paramstring`` attribute into name → raw value entries."""

    def __init__(self, line: str):

        for row in line.split(";"):

            if row == "":

                continue

            name, separator, value = row.partition("=")

            if not separator:

                continue

            self[name] = value
