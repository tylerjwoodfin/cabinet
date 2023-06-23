"""
A MongoDB Experiment
"""
import json
import ast
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


class Cabinet:
    """
    Cabinet class
    """

    uri = ("mongodb+srv://<username goes here>:<password goes here>"
           "@<cluster name goes here>.1jxchnk.mongodb.net/cabinet?retryWrites=true&w=majority")

    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client.cabinet

    def merge_nested_data(self, existing_data, new_data):
        """
        Merge Nested Data
        """
        merged_data = {}

        for key, value in existing_data.items():
            if key in new_data and isinstance(value, dict) and isinstance(new_data[key], dict):
                merged_data[key] = self.merge_nested_data(value, new_data[key])
            else:
                merged_data[key] = value

        for key, value in new_data.items():
            if key not in merged_data:
                merged_data[key] = value
            else:
                if isinstance(value, dict) and isinstance(merged_data[key], dict):
                    merged_data[key] = self.merge_nested_data(merged_data[key], value)
                else:
                    merged_data[key] = value

        return merged_data


    def put(self, *attribute, value=None, is_print=False):
        """
        Adds or replaces a property
        """

        def parse_arg(value):
            """
            Infer the value type (e.g. 2 will not be parsed as a string)
            """
            if value == "null":
                return None
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    if value.lower() == 'true':
                        return True
                    if value.lower() == 'false':
                        return False
                    try:
                        return ast.literal_eval(value)
                    except (SyntaxError, ValueError):
                        return value

        custom_filter = {}

        if value is None:  # Check if value argument is None
            value = parse_arg(attribute[-1])

        cache = attribute[-1]
        json_structure = {}
        for item in reversed(attribute[:-1]):
            try:
                json_structure = {}
                json_structure[item] = cache
                cache = json_structure
            except TypeError as error:
                print(error)

        print(json_structure)

        existing_data = self.db.cabinet.find_one({}, {"_id": 0})

        # Merge the new data with the existing data
        update = {"$set": {}}

        if len(attribute) > 2:
            update["$set"][attribute[0]] = self.merge_nested_data(existing_data.get(
                attribute[0], {}), json_structure[attribute[0]])
        else:
            update = {"$set": json_structure}

        result = self.db.cabinet.update_many(custom_filter, update)

        print(f"Modified {result.modified_count} item(s)")
        print(
            f"{' -> '.join(attribute[:-1])} set to {value}\n")

        return value


    def ping(self):
        """
        Send a ping to verify successful connection
        """
        try:
            self.client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as error:
            print(error)

    def export(self):
        """
        Exports all data to JSON
        """
        data = self.db.cabinet.find_one({}, {"_id": 0})
        json_data = json.dumps(data, indent=4)

        with open('database.json', 'w', encoding='utf-8') as file:
            file.write(json_data)


cab = Cabinet()
# Update the value of "entry light"
cab.put("test8", False)
cab.export()
