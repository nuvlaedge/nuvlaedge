# NuvlaEdge System Manager Unit Tests

This folder contains all the unit tests available for the NuvlaEdge System Manager. For each module, there is a respective
test file, where each module class and/or function is tested.

## Run the tests


To run the tests, make sure you've installed the dependencies from `requirements.tests.txt`:

```shell
# from the <project_root>/code folder
pip install -r requirements.tests.txt
```

and then run:

```shell
# from the <project_root>/code folder
python -m unittest tests/test_<filename>.py -v
```

or, if a report is needed:

```shell
pytest --junitxml=test-report.xml
```
