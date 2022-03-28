from typing import Union, List, Optional
from sqlalchemy.orm import validates
from app import db, ma
from exceptions import PlateNotFound, InvalidWellContents, WellOutOfBounds, InvalidPlateData


# Models
class Well(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_id = db.Column(db.Integer, db.ForeignKey("plate.id"))

    # my personal preference here is to root the physical well mapping in
    # a single value rather than the row/col paradigm. a user would still
    # need and probably prefer the row/col or even "humanized" (A1, B8, etc)
    # formats but i think the conversion can be pretty easily standardized
    index = db.Column(db.Integer)
    cell_line = db.Column(db.String)

    def __init__(self,
                 plate_id: int,
                 index: int,
                 cell_line: Optional[str] = None,
                 chemicals: Optional[Union[List[str], str]] = None,
                 concentrations: Optional[Union[List[float], float]] = None
                 ):
        self.plate_id = plate_id
        self.cell_line = cell_line
        self.index = index
        db.session.add(self)
        db.session.commit()

        if chemicals:
            self.add_chemicals(chemicals, concentrations)

    @validates('cell_line')
    def validate_cell_line(self, key, cell_line):
        if cell_line:
            try:
                assert cell_line.startswith('c')
                for char in cell_line[1:]:
                    assert char.isdigit()
                return cell_line
            except AssertionError:
                raise InvalidWellContents(
                    f"'{cell_line}' is not a valid cell line identifier."
                    f" A valid cell line must begin with 'c' and be followed by a number sequence."
                )
        else:
            return cell_line

    @validates('concentrations')
    def validate_concentrations(self, key, concentrations):
        try:
            if type(concentrations) == list:
                assert all([conc > 0 for conc in concentrations])
            else:
                assert concentrations > 0
            return concentrations
        except AssertionError:
            raise InvalidWellContents(
                f"Concentrations must be greater than 0"
            )

    def add_chemicals(self,
                      chemicals: Union[List[str], str],
                      concentrations: Union[List[float], float],
                      overwrite_existing: bool = True):
        # standardize inputs of chemicals/concentrations
        if type(chemicals) == str:
            chemicals = [chemicals]
        if concentrations:
            if type(concentrations) == float or type(concentrations) == int:
                concentrations = [concentrations]
            if len(chemicals) != len(concentrations):
                if len(concentrations) != 1:
                    # raise error for putting bad combination of chemicals and concentrations
                    raise InvalidWellContents(
                        f"If multiple concentrations are submitted, there must be 1 or the same number of concentrations as chemicals."
                    )
                else:
                    concentrations = concentrations * len(chemicals)
            for conc in concentrations:
                if conc < 0:
                    raise InvalidWellContents(
                        f"submitted concentration {conc} is less than 0. Concentrations must be positively signed."
                    )

        # If an over-write is needed, remove existing entries for this
        # well index from the chemicals in wells table
        if overwrite_existing:
            existing_chemicals_in_well = ChemicalInWell.query.filter_by(well_id=self.id)
            if existing_chemicals_in_well:
                for chemical_in_well in existing_chemicals_in_well:
                    db.session.delete(chemical_in_well)
                    db.session.commit()

        # for each specified chemical
        for i, chemical_str_id in enumerate(chemicals):
            if not concentrations:
                concentration = None
            else:
                concentration = concentrations[i]
            if Chemical.query.filter_by(str_id=chemical_str_id).first():
                # chemical already exists, just add entry in association table
                new_chemical_in_well = ChemicalInWell(
                    chemical_str_id=chemical_str_id,
                    well_id=self.id,
                    concentration=concentration
                )
                db.session.add(new_chemical_in_well)
                db.session.commit()
            else:
                # have to make new chemical entry before creating association table entry
                new_chemical = Chemical(chemical_str_id)
                db.session.add(new_chemical)
                db.session.commit()
                new_chemical_in_well = ChemicalInWell(
                    chemical_str_id=new_chemical.str_id,
                    well_id=self.id,
                    concentration=concentration
                )
                db.session.add(new_chemical_in_well)
                db.session.commit()


class Plate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    size = db.Column(db.Integer)
    name = db.Column(db.String(100))
    wells = db.relationship("Well", backref=db.backref('plate'))
    _size_shape_map = {
        96: "12x8",
        384: "24x16",
        1536: "48x24"
    }

    def __init__(self, name: str, size: int):
        self.size = size
        self.name = name

    @validates('size')
    def validate_size(self, key, size):
        try:
            assert size in self._size_shape_map.keys()
            return size
        except AssertionError:
            raise InvalidPlateData(
                f"{size} is not a valid plate size."
            )

    def make_empty_well(self, index: int, overwrite: bool = True) -> Well:
        """Used to return a new well with minimal data if one doesnt already exist"""
        self.check_index(index)
        if Well.query.filter_by(plate_id=self.id, index=index).first():
            if overwrite:
                well_to_delete = Well.query.filter_by(plate_id=self.id, index=index).first()
                db.session.delete(well_to_delete)
                db.session.commit()
            else:
                raise InvalidWellContents(
                    f"There is already a well here that you don't want to over write: plate id: {self.id}, index: {index}"
                )
        new_well = Well(self.id, index)
        db.session.add(new_well)
        db.session.commit()
        return new_well

    def set_well_data(self, index: int, chemicals: Union[List[str], str], concentrations: Union[List[float], float], **kwargs) -> Well:
        """makes it easy to flexibly modify properties of well objects via their parent plate"""
        self.check_index(index)
        if Well.query.filter_by(plate_id=self.id, index=index).first():
            well_to_update = Well.query.filter_by(plate_id=self.id, index=index).first()
            for kw, val in kwargs.items():
                setattr(well_to_update, kw, val)
            well_to_update.add_chemicals(chemicals=chemicals, concentrations=concentrations)
            db.session.commit()
            return well_to_update
        else:
            new_well = Well(plate_id=self.id,
                            index=index,
                            chemicals=chemicals,
                            concentrations=concentrations,
                            **kwargs)
            db.session.add(new_well)
            db.session.commit()
            return new_well

    @property
    def num_rows(self) -> int:
        return int(self._size_shape_map.get(self.size).split('x')[1])

    @property
    def num_cols(self) -> int:
        return int(self._size_shape_map.get(self.size).split('x')[0])

    def well(self, index: int) -> Well:
        """get the well with the specified index if it exists or make + return a new empty well"""
        self.check_index(index)
        if Well.query.filter_by(plate_id=self.id, index=index).first():
            return Well.query.filter_by(plate_id=self.id, index=index).first()
        else:
            return self.make_empty_well(index=index)

    def get_index(self, row: int, col: int) -> int:
        """
        A1 -> index 0, counting horizontally and then moving to the next row down.
         rows, columns, and generic index are 0-indexed
         """
        index = (self.num_cols - 1) * row + col
        self.check_index(index)
        return index

    def all_wells(self) -> List[Well]:
        all_wells = []
        for i in range(self.size):
            all_wells.append(self.well(i))
        return all_wells

    def check_index(self, index):
        if index > self.size - 1 or index < 0:
            raise WellOutOfBounds(
                f"Invalid well index '{index}' for this plate type. Well "
                f"indices must be integers less than the size of the "
                f"plate and greater than 0."
            )


class Chemical(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    str_id = db.Column(db.String, unique=True)

    # Room for lots of other known chemical properties here

    def __init__(self, str_id: str):
        self.str_id = str_id

    @validates('str_id')
    def validate_str_id(self, key, str_id):
        try:
            assert str_id.startswith('O')
            for char in str_id[1:]:
                assert char.isdigit()
            return str_id
        except AssertionError:
            raise InvalidWellContents(
                f"'{str_id}' is not a valid chemical identifier."
                f" A valid chemical must begin with 'O' and be followed by a number sequence."
            )


class ChemicalInWell(db.Model):

    # relational columns
    chemical_str_id = db.Column(db.String, db.ForeignKey('chemical.str_id'), primary_key=True)
    well_id = db.Column(db.Integer, db.ForeignKey('well.id'), primary_key=True)

    # Data which only exists when a link exists between well and chemical
    concentration = db.Column(db.Float)

    # support M2M relationship
    chemical = db.relationship("Chemical", backref=db.backref('wells', cascade="all", passive_deletes=True))
    well = db.relationship("Well", backref=db.backref('chemicals', cascade="all", passive_deletes=True))

    def __init__(self, chemical_str_id: str, well_id: int, concentration: float):
        self.chemical_str_id = chemical_str_id
        self.well_id = well_id
        self.concentration = concentration


class DoseResponseCurve(db.Model):
    """meant to serve as an anchor for post-assay analysis to quickly get assay curves"""
    id = db.Column(db.Integer, primary_key=True)
    plate_id = db.Column(db.Integer, db.ForeignKey('plate.id'))
    starting_well_index = db.Column(db.Integer)
    n_points = db.Column(db.Integer)
    max_concentration = db.Column(db.Float)
    min_concentration = db.Column(db.Float)
    chemical = db.Column(db.String, db.ForeignKey('chemical.str_id'))
    orientation = db.Column(db.String)

    def __init__(self,
                 plate_id: int,
                 starting_well_index: int,
                 n_points: int,
                 max_concentration: float,
                 min_concentration: float,
                 chemical: str,
                 orientation: str = 'horizontal'
                 ):
        self.plate_id = plate_id
        self.starting_well_index = starting_well_index
        self.n_points = n_points
        self.max_concentration = max_concentration
        self.min_concentration = min_concentration
        self.chemical = chemical
        self.orientation = orientation

    @validates('plate_id')
    def validate_plate_id(self, key, plate_id):
        try:
            assert Plate.query.get(plate_id)
            return plate_id
        except AssertionError:
            raise PlateNotFound(
                f"Plate '{plate_id}' does not exist yet so you can't make a DRC on it."
            )

    @validates('starting_well_index')
    def validate_starting_well_index(self, key, starting_well_index):
        if starting_well_index > Plate.query.get(self.plate_id).size - 1:
            raise WellOutOfBounds(
                f"This curve doesnt fit on the plate!"
            )
        return starting_well_index

    @validates('max_concentration')
    def validate_min_concentration(self, key, max_concentration):
        self.validate_conc(max_concentration)
        return max_concentration

    @validates('min_concentration')
    def validate_min_concentration(self, key, min_concentration):
        self.validate_conc(min_concentration)
        if min_concentration >= self.max_concentration:
            raise InvalidWellContents(
                f"Invalid curve concentrations. The max concentration must be greater than the min concentration."
            )
        return min_concentration

    @validates('orientation')
    def validate_orientation(self, key, orientation):
        if orientation not in ['vertical', 'horizontal']:
            raise InvalidPlateData(
                f"{orientation} is not a valid orientation. must be 'horizontal' or 'vertical'"
            )

    @staticmethod
    def validate_conc(concentration):
        if concentration < 0:
            raise InvalidWellContents(
                f"Specified concentrations may not be negative."
            )

    def populate_wells(self):
        # Do some business logic to get the list of wells/concentrations
        list_of_concentrations = self.calculate_curve()
        list_of_wells = self.curve_wells

        # make/overwrite wells in those locations
        # setting cell_line will happen in bulk outside of the dose response curve.
        # the drc should only know about the chemical information
        for i, well in enumerate(list_of_wells):
            Plate.query.get(self.plate_id).set_well_data(
                index=well.index,
                chemicals=self.chemical,
                concentrations=list_of_concentrations[i]
            )

    def calculate_curve(self) -> List[float]:
        curve_span = (self.max_concentration - self.min_concentration)
        regular_increments = curve_span / (self.n_points - 1)
        curve_concentrations = []
        for p in range(self.n_points):
            next_point = self.max_concentration - p * regular_increments
            curve_concentrations.append(next_point)
        return curve_concentrations

    @property
    def curve_wells(self) -> List[Well]:
        try:
            # this logic holds for horizontal curves, but could add for vertical curve capabilities
            curve_wells = []
            for w_index in range(self.starting_well_index, self.ending_well_index):
                curve_wells.append(self.plate.well(w_index))
            return curve_wells
        except ValueError as e:
            if "size" in e:
                raise WellOutOfBounds(
                    f"This dose response curve runs off the plate. "
                    f"The following error was generated in the making of this DRC: {e}"
                )

    @property
    def ending_well_index(self) -> int:
        return self.starting_well_index + self.n_points

    @property
    def plate(self) -> Plate:
        return Plate.query.get(self.plate_id)


# Schemas
class ChemicalSchema(ma.Schema):
    class Meta:
        fields = ('str_id', 'id')


class ChemicalInWellSchema(ma.Schema):
    class Meta:
        fields = ('chemical_str_id', 'concentration')


class WellSchema(ma.Schema):
    chemicals = ma.Nested(ChemicalInWellSchema, many=True)

    class Meta:
        fields = ('plate_id', 'index', 'chemicals', 'cell_line')


class PlateSchema(ma.Schema):
    wells = ma.Nested(WellSchema, many=True)
    class Meta:
        fields = ('id', 'size', 'name', 'wells')


# Init Schemas
plate_schema = PlateSchema()
plates_schema = PlateSchema(many=True)
well_schema = WellSchema()
wells_schema = WellSchema(many=True)
chemicals_schema = ChemicalSchema(many=True)