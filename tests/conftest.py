import csv
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session')
def spark():
    if not os.getenv('JAVA_HOME'):
        found = list((ROOT / '.runtime').glob('jdk-17*'))
        if found:
            os.environ['JAVA_HOME'] = str(found[0])
    if os.name == 'nt' and not os.getenv('HADOOP_HOME'):
        os.environ['HADOOP_HOME'] = str(ROOT / '.hadoop')
        os.environ['PATH'] = str(ROOT / '.hadoop/bin') + os.pathsep + os.environ['PATH']
    from app.services.spark_service import get_spark_session
    session = get_spark_session()
    yield session


@pytest.fixture
def raw_factory(spark, tmp_path):
    from app.services.data_pipeline import COLUMNS
    def make(overrides):
        base = {'Order Id':'1','Order Item Id':'1','order date (DateOrders)':'1/1/2017 10:00',
                'Days for shipping (real)':'5','Days for shipment (scheduled)':'4',
                'Late_delivery_risk':'1','Delivery Status':'Late delivery','Order Status':'COMPLETE',
                'Market':'Europe','Order Region':'Western Europe','Shipping Mode':'Standard Class',
                'Customer Segment':'Consumer','Type':'DEBIT','Order Item Quantity':'1','Sales':'100',
                'Order Item Total':'90', 'Order Country':'España'}
        path = tmp_path / 'fixture.csv'
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[*COLUMNS, 'Order Country'])
            writer.writeheader()
            writer.writerows([{**base, **r} for r in overrides])
        return spark.read.option('header', True).csv(str(path))
    return make
