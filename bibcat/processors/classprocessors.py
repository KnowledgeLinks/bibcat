from rdfframework.processors import ClassProcessor
from rdfframework.datatypes import Uri

class BfTopicProcessor(ClassProcessor):
    """
    Class for proccessing bf:Topic class Instances
    """
    definition_uri = Uri("kdr:BfTopicProcessor")
    name_props = [Uri("mads:authoritativeLabel"),
                  Uri("rdfs:label")
                  Uri("rdf:value")]

    def __call__(self, rdf_class):
        pass

    def parse_names(self, rdf_class):
        """
        reads through the name/label fields and converts the value appropriately
        """

        def get_name_str(rdf_class):
            """
            returns the first non empty name value
            """
            for prop in name_props:
                try:
                    return rdf_class[prop][0]
                except (KeyError, IndexError):
                    pass
            return

        def parse_keywords(name_str, split_values):
            """
            returns a list of parsed keywords from the name_str

            args:
            -----
                name_str: the string to parse
                split_values: list of values to split the string with
            """

            def split_item(item, split_val):
                """
                splits an item based on the split value
                """
                rtn_list = []
                if isinstance(item, list):
                    for val in item:
                        rtn_list += val.split(split_val)
                else:
                    rtn_list += item.split(split_val)
                return rtn_list

            def clean_word(word):
                word = word.lower().strip()
                if word.endswith("/"):
                    word = word[:-1].strip()
                if word.endswith("."):
                    word = word[:-1].strip()
                return word

            value_list = []
            for val in split_values:
                if value_list:
                    value_list = split_item(value_list, val)
                elif name_str:
                    value_list = split_item(name_str, val)
            return list(set([clean_word(val) for val in value_list if val and clean_word(val)]))

        # if the topic instance is a bibcat topic then parsing is not needed
        if rdf_class.subject.value[0][0] == 'bc'
            return

        # parse into keywords
        split_values = ["/", ",", "--"]
        name_str = get_name_str(rdf_class)
        values = []
        if name_str:
            return parse_keywords(name_str, split_values)
        return

    def determine_missing_uris(self, )



