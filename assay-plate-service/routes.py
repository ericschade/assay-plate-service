from app import app, db
from flask import request, jsonify
from exceptions import PlateNotFound, InvalidWellContents, WellOutOfBounds
from model import Plate, Well, DoseResponseCurve, Chemical, plate_schema, plates_schema, well_schema, wells_schema, chemicals_schema


# Make a new plate
@app.route('/plates', methods=['POST'])
def add_plate():
    name = request.json['name']
    size = request.json['size']

    # create new object
    try:
        new_plate = Plate(name=name, size=size)

        # insert to db plate table
        db.session.add(new_plate)
        db.session.commit()
        # new_plate.make_all_wells_empty()
        return plate_schema.jsonify(new_plate)
    except Exception as e:
        return jsonify(
            str(e)
        )


# Get plate info
@app.route('/plates', methods=['GET'])
def get_all_plates():
    # return serialized plate object
    plates = Plate.query.all()
    return plates_schema.jsonify(plates)


# Get plate info
@app.route('/plates/<plate_id>', methods=['GET'])
def get_plate(plate_id):
    # return serialized plate object
    plate = Plate.query.get(plate_id)
    if not plate:
        raise PlateNotFound(f"{plate_id} doesn't exist yet!")
    return plate_schema.jsonify(plate)


# Make a new well
@app.route('/plates/<plate_id>/wells', methods=['POST'])
def populate_well(plate_id):
    row = request.json['row']
    col = request.json['col']
    cell_line = request.json.get('cell_line')
    chemical = request.json.get('chemical')
    concentration = request.json.get('concentration')
    if concentration and not chemical:
        raise InvalidWellContents(
            f"No concentration may be specified without assigning a chemical to the well."
        )


    # create new object
    plate = Plate.query.get(plate_id)
    if not plate:
        raise PlateNotFound(
            f"Plate {plate_id} doesn't exist yet!"
        )
    well_index = plate.get_index(row, col)
    well_to_populate = plate.well(well_index)
    well_to_populate.cell_line = cell_line
    well_to_populate.add_chemicals(chemical, concentration)
    db.session.add(well_to_populate)
    db.session.commit()
    return well_schema.jsonify(well_to_populate)


# Get all wells for a plate
@app.route('/plates/<plate_id>/wells', methods=['GET'])
def view_wells(plate_id):
    all_wells = Well.query.filter_by(plate_id=plate_id)
    return wells_schema.jsonify(all_wells)


# Delete data from a well
@app.route('/plates/<plate_id>/wells/<row>/<col>', methods=['DELETE'])
def delete_well(plate_id, row, col):
    plate_of_well = Plate.query.get(plate_id)
    index_to_delete = plate_of_well.get_index(row=int(row), col=int(col))
    well_to_delete = plate_of_well.well(index_to_delete)
    db.session.delete(well_to_delete)
    db.session.commit()
    # plate_of_well.make_empty_well(index_to_delete, overwrite=True)
    return jsonify(f"successfully deleted well ({row}, {col}) from plate {plate_id}!")


# Get all chemicals that have ever been registered
@app.route('/chemicals', methods=['GET'])
def view_all_chemicals():
    all_chemicals = Chemical.query.all()
    return chemicals_schema.jsonify(all_chemicals)


# Fill a plate with dose response Curve and control chemical data
@app.route('/plates/<plate_id>/drc', methods=['POST'])
def assign_dose_response_curves(plate_id):

    plate = Plate.query.get(plate_id)
    # Unpack the request
    cell_line = request.json['cell_line']
    chemicals = request.json['chemicals']
    min_concentration = request.json['min_concentration']
    max_concentration = request.json['max_concentration']
    n_points = request.json['n_points']
    control_chemical = request.json['control_chemical']
    control_concentration = request.json['control_concentration']

    if len(chemicals) * n_points > plate.size:
        raise WellOutOfBounds(
            f"Too many wells are needed to fit onto plate {plate.name} alone. "
            f"Consider reducing the number of chemicals or the number of points in the response curve."
        )
    # try:
    # Make a bunch of new drcs
    starting_well_index = 0
    for chemical in chemicals:
        new_drc = DoseResponseCurve(
            plate_id=plate_id,
            starting_well_index=starting_well_index,
            min_concentration=min_concentration,
            max_concentration=max_concentration,
            chemical=chemical,
            n_points=n_points
        )
        starting_well_index += n_points
        db.session.add(new_drc)
        db.session.commit()

    # populate the curve wells. Doing this after defining them to avoid
    # partial data update due to an error
    for drc in DoseResponseCurve.query.filter_by(plate_id=plate_id):
        drc.populate_wells()

    # Populate control wells
    for index in range(starting_well_index, plate.size):
        plate.set_well_data(index=index, chemicals=control_chemical, concentrations=control_concentration)
        db.session.commit()
    # assign cell line
    for well in plate.all_wells():
        well.cell_line = cell_line
        db.session.commit()
    return jsonify(f"successfully added {n_points} point drc's to plate {plate.name} for {len(chemicals)} chemicals!")