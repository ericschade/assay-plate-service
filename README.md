# assay-plate-service
Create and customize assay plates with experimentally relevant well contents.

### Running the App:
```
pip install -r requirements-pip3.txt
cd assay-plate-service
```

```
python
from app import db
db.create_all()
```

`python app.py`

### Notes related to the take-home problem:

 - All POST requests will successfully execute exactly as formatted in the prompt
 - There are are two discrepencies between the way the data is held/serialized when compared to the prompt:
    - Additional feature - multiple chemicals can be placed in a single well for combinatorial screening applications by making the "chemical" and "concentration" fields into lists. It is still ok to POST non-list data to thsoe fields without error but well schema returned by 'GET' requests come with a list of serialized chemical/concentration pairs rather than strings
    - Change to schema - the plate layout data is held in a field called 'wells' in the plate GET response rather than 'plate', which made the most sense to me in lieu of knowing exactly what should be in the 'plate' field.

 - 8 Endpoints defined:

 '/plates/id'    'GET'
        - get specified plate
        - error if plate not defined yet

 '/plates/id'   'POST'
        - make new empty plate

 '/plates/id/wells' 'POST'
        - add info to a well in the specified plate
        - error if plate doesnt exist or if well is out of bounds

 '/plates/id/wells/row/col' 'DELETE'
        - delete an existing well

 '/plates/id/drc'   'POST'
        - populate wells on the specified plate with dose response curves
        - error if the curves dont fit on one plate

 # extras

 '/plates'    'GET'
        - get data for all existing plates

 '/plates/plate_id/wells' 'GET'
        - get all wells for the specified plate
        - error if plate doesn't exist

 '/chemicals' 'GET'
        - get all chemicals that are in all wells across all plates. not tied to concentration



