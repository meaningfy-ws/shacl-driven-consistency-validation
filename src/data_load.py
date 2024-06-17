import pandas as pd


########################################################
###########Load Conceptual Mapping Sheet################
########################################################

class dataLoader():
    def __init__(self, file_path):
        # load the data
        self.data = pd.read_excel(file_path, 
                                  sheet_name = ["Metadata", "Rules", "CL1 Controlled List of Roles", "CL2 Controlled List for Organis"])
        self.metadataDf, self.rulesDf, self.cl1Df, self.cl2Df = self.data["Metadata"], self.data["Rules"], self.data["CL1 Controlled List of Roles"], self.data["CL2 Controlled List for Organis"]
        # release the memory
        del self.data
        
    def load_metadata(self):

        metaData_info = f"""The SHACL shapes graph is automatic translated from the Conceptual Mapping which has: 
        Identifier: {self.metadataDf.loc[self.metadataDf['Field'] == 'Identifier', 'Value examples'].values[0]}, 
        Description {self.metadataDf.loc[self.metadataDf['Field'] == 'Description', 'Value examples'].values[0],},
        Mapping Version {self.metadataDf.loc[self.metadataDf['Field'] == 'Mapping Version', 'Value examples'].values[0]}, and
        EPO version {self.metadataDf.loc[self.metadataDf['Field'] == 'EPO version', 'Value examples'].values[0]}."""

        self.baseXpath = self.metadataDf.loc[self.metadataDf['Field'] == 'Base XPath', 'Value examples'].values[0]
        
        return metaData_info, self.baseXpath

    def load_rules(self):
        self.rulesDf.rename(columns=self.rulesDf.iloc[0], inplace = True)
        self.rulesDf.drop([0], inplace = True)
        
        Field_XPath = self.rulesDf["Field XPath (M)"].tolist()
        Class_path = self.rulesDf["Class Path (M)"].tolist()
        Property_path = self.rulesDf["Property Path (M)"].tolist()

        return Field_XPath, Class_path, Property_path

    def load_controlled_list(self):
        pass


# dL = dataLoader("TED/conceptual_mappings.xlsx")
# data = dL.load_rules()
# print(data)