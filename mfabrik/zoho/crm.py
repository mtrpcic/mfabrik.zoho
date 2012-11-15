"""

    Zoho CRM API bridge.

"""

__copyright__ = "2010 mFabrik Research Oy"
__author__ = "Mikko Ohtamaa <mikko@mfabrik.com>"
__license__ = "GPL"
__docformat__ = "Epytext"


try:
    from xml import etree
    from xml.etree.ElementTree import Element, tostring, fromstring
except ImportError:
    try:
        from lxml import etree
        from lxml.etree import Element, tostring, fromstring
    except ImportError:
        raise RuntimeError("XML library not available:  no etree, no lxml")
   
from core import Connection, ZohoException, decode_json

class CRM(Connection):
    """ CRM specific Zoho APIs mapped to Python """
    
    # Fixed
    def get_service_name(self):
        """ Called by base class """
        return "ZohoCRM"
    
    # Fixed
    def check_successful_xml(self, response):
        """ Make sure that we get "succefully" response.
        
        Throw exception of the response looks like something not liked.
        
        @raise: ZohoException if any error
        
        @return: Always True
        """

        # Example response
        # <response uri="/crm/private/xml/Leads/insertRecords"><result><message>Record(s) added successfully</message><recorddetail><FL val="Id">177376000000142007</FL><FL val="Created Time">2010-06-27 21:37:20</FL><FL val="Modified Time">2010-06-27 21:37:20</FL><FL val="Created By">Ohtamaa</FL><FL val="Modified By">Ohtamaa</FL></recorddetail></result></response>

        root = fromstring(response)
            
        # Check error response
        # <response uri="/crm/private/xml/Leads/insertRecords"><error><code>4401</code><message>Unable to populate data, please check if mandatory value is entered correctly.</message></error></response>
        for error in root.findall("error"):
            print "Got error"
            for message in error.findall("message"):
                raise ZohoException(message.text)
        
        return True

    # Fixed
    def add_note(self, entity_id, title, body):
        attributes = {
            "entityId": entity_id,
            "Note Title": title,
            "Note Content": body
        }

        root = Element("Notes")
        row = Element("row", no="1")
        root.append(row)

        for key, value in attributes.items():
            fl = Element("fl", val=key)
            fl.text = value
            row.append(fl)

        post_params = {
            "newFormat": 1
        }

        url = "https://crm.zoho.com/crm/private/xml/Notes/insertRecords"
        response = self.do_xml_call(url, post_params, root)
        return self.check_successful_xml(response)

    def update_note(self, note_id, title, body):
        attribues = {
            "Note Title": title,
            "Note Content": body
        }

        post_params = {
            "newFormat": 1,
            id: note_id
        }

        root = Element("Notes")
        row = Element("row", no="1")
        root.append(row)

        for key, value in attributes.items():
            fl = Element("fl", val=key)
            fl.text = value
            row.append(fl)

        url = "https://crm.zoho.com/crm/private/xml/Notes/updateRecords"
        response = self.do_xml_call(url, post_params, root)
        return self.check_successful_xml(response)


    def get_notes_for_entity(self, entity_id):
        post_params = {
            "newFormat": 1,
            "id": entity_id,
            "parentModule": "All"
        }
        url = "https://crm.zoho.com/crm/private/json/Notes/getRelatedRecords"
        data = self.do_call(url, post_params)

        output = []
        print "Data...."
        print data
        for row in data["response"]["result"]["Notes"]["row"]:
            item = {}
            for cell in row["FL"]:
                item[cell["val"]] = cell["content"]
            
            output.append(item)
            
        return output

    # Fixed
    def update_records(self, table, id, data=[], additional_post_params={}):
        self.ensure_opened()
        resource = table.capitalize()
        root = Element(resource)

        row_count = 1

        for record in data:
            row = Element("row", no=str(row_count))
            root.append(row)

            for key, value in record.items():
                fl = Element("fl", val=key)
                fl.text = value
                row.append(fl)

            row_count += 1

        post_params = {
            "newFormat": 1,
            "id": id
        }

        post_params.update(additional_post_params)

        url = "https://crm.zoho.com/crm/private/xml/%s/updateRecords" % resource

        response = self.do_xml_call(url, post_params, root)
        return self.check_successful_xml(response)

    
    def insert_records(self, leads, extra_post_parameters={}):        

        self.ensure_opened()
        
        root = Element("Leads")

        # Row counter
        no = 1

        for lead in leads:
            row = Element("row", no=str(no))
            root.append(row)

            assert type(lead) == dict, "Leads must be dictionaries inside a list, got:" + str(type(lead))
        
            for key, value in lead.items():
                # <FL val="Lead Source">Web Download</FL>
                # <FL val="First Name">contacto 1</FL>
                fl = Element("fl", val=key)
                fl.text = value
                row.append(fl)
                
            no += 1

        post = {
            'newFormat':    1,
            'duplicateCheck':   2
        }

        post.update(extra_post_parameters)
        
        response = self.do_xml_call("https://crm.zoho.com/crm/private/xml/Leads/insertRecords", post, root)

        self.check_successful_xml(response)
                
        return self.get_inserted_records(response)
        
    
    def get_inserted_records(self, response):
        """
        @return: List of record ids which were created by insert recoreds
        """
        root = fromstring(response)
        
        records = []
        for result in root.findall("result"):
            for record in result.findall("recorddetail"):
                record_detail = {}
                for fl in record.findall("FL"):
                    record_detail[fl.get("val")] = fl.text
                records.append(record_detail)
        return records
        
    # Fixed
    def get_records(self, table="leads", columns=[], parameters={}):
        """ 
        
        http://zohocrmapi.wiki.zoho.com/getRecords-Method.html
        
        @param selectColumns: String. What columns to query. For example query format,
            see API doc. Default is leads(First Name,Last Name,Company).
        
        @param parameters: Dictionary of filtering parameters which are part of HTTP POST to Zoho.
            For example parameters see Zoho CRM API docs.
        
        @return: Python list of dictionarizied leads. Each dictionary contains lead key-value pairs. LEADID column is always included.

        """

        self.ensure_opened()

        if isinstance(columns, dict):
            columns = ",".join(columns)
            select_columns = "%s(%s)" % (resource, columns)
        else:
            select_columns = "All"

        resource = table.capitalize()

        post_params = {
            "selectColumns": select_columns,
            "newFormat": 2
        }
        post_params.update(parameters)

        url = "https://crm.zoho.com/crm/private/json/%s/getRecords" % resource
        response = self.do_call(url, post_params)
        
        # raw data looks like {'response': {'result': {'Leads': {'row': [{'FL': [{'content': '177376000000142085', 'val': 'LEADID'}, ...
        data =  decode_json(response)
        
        # Sanify output data to more Python-like format
        output = []
        for row in data["response"]["result"][resource]["row"]:
            item = {}
            for cell in row["FL"]:
                item[cell["val"]] = cell["content"]
            
            output.append(item)
            
        return output  
                
    def delete_record(self, id, parameters={}):
        """ Delete one record from Zoho CRM.
                        
        @param id: Record id
        
        @param parameters: Extra HTTP post parameters        
        """
        
        self.ensure_opened()
    
        post_params = {}
        post_params["id"] = id
        post_params.update(parameters)
        
        response = self.do_call("https://crm.zoho.com/crm/private/xml/Leads/deleteRecords", post_params)
        
        self.check_successful_xml(response)
        