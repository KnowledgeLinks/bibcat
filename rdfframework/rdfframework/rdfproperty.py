class RdfProperty(object):
    def __init__(self, prop_list, data=None, subject_uri=None):
        for key, value in prop_list.items():
            setattr(self, key, value)
        self.data = data
        self.old_data = None
        self.processed_data = None
        self.query_data = None
        self.editable = True
        self.doNotSave = False
        #self.subject_uri = subject_uri
        if not hasattr(self, "kds_processors"):
            self.kds_processors = []