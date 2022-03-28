from app import app


# Custom Exceptions
class PlateNotFound(Exception):
    code = 404
    description = "Plate not found"


class WellOutOfBounds(Exception):
    code = 400
    description = "Well out of bounds"


class InvalidWellContents(Exception):
    code = 400
    description = "Invalid well contents"


class InvalidPlateData(Exception):
    code = 400
    description = "Invalid Data submitted"


# Error Handlers
@app.errorhandler(KeyError)
def bad_request_handler(error):
    return f"Missing Required Field!  400: Request missing the following field: {error}"


@app.errorhandler(PlateNotFound)
def plate_not_found_handler(error):
    return f"Plate Not Found Error: {error.code} - {str(error)}"


@app.errorhandler(WellOutOfBounds)
def well_out_of_bounds_handler(error):
    return f"Well Out of Bounds Error: {error.code} - {str(error)}"


@app.errorhandler(InvalidWellContents)
def invalid_well_contents_handler(error):
    return f"Invalid Well Contents Error: {error.code} - {str(error)}"


@app.errorhandler(InvalidPlateData)
def invalid_plate_data_handler(error):
    return f"Invalid Plate Data Error: {error.code} - {str(error)}"


