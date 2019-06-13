def test_get_all_templates(client):
    # Call the get report-templates endpoint
    rv = client.get('/api/v1/templates')
    assert b'"payment_receipt_v1"' in rv.data
    assert 'payment_receipt_v1' in rv.json['report-templates']
    assert 'payment_receipt_v2' in rv.json['report-templates']
    assert rv.status_code == 200

def test_get_two_templates(client):
    # Call the get report-templates endpoint
    rv = client.get('/api/v1/templates?name=payment_receipt_v2')
    assert rv.status_code == 200

def test_get_one_templates(client):
    # Call the get report-templates endpoint
    rv = client.get('/api/v1/templates?name=donotexist')
    assert rv.status_code == 404
