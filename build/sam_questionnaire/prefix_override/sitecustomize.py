import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/lair/DataCollection/SAM_questionnaire/install/sam_questionnaire'
