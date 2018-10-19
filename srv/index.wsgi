import sys
import os
import ctypes
import time
import json
from json import JSONDecodeError
from types import SimpleNamespace
from owslib.feature.wfs110 import WebFeatureService_1_1_0
import hashlib
import pickle
import urllib



global WFS
sys.path.append(os.path.join('C', os.sep, 'Apache24','htdocs', 'lib'))
print("sys.path =", sys.path)
from makeBoreholes import get_blob_boreholes, get_boreholes_list, get_json_input_param
from db.db_tables import QueryDB

g_BLOB_DICT = {}
g_BOREHOLE_DICT = {}
WFS = None


# Maximum number of boreholes processed
MAX_BOREHOLES = 9999

# Timeout for querying WFS services (seconds)
WFS_TIMEOUT = 6000



    
def get_file_hash(input_str):
    h = hashlib.new('md5')
    h.update(bytes(input_str, 'utf-8'))
    return h.hexdigest()


Param = get_json_input_param(os.path.join('C', os.sep, 'Apache24', 'htdocs', 'input', 'NorthGawlerConvParam.json'))

# I have to override 'WebFeatureService' because a bug in owslib makes 'pickle' unusable 
# TODO: Fix the bug
class MyWebFeatureService(WebFeatureService_1_1_0):
    def __new__(self, url, version, xml, parse_remote_metadata=False, timeout=30, username=None, password=None):
        obj=object.__new__(self)
        return obj
        
    def __getnewargs__(self):
        return ('','',None)
    

print("opening WFS")
print("os.getcwd()=", os.getcwd())
CACHE_DIR = os.path.join('C', os.sep, 'Apache24', 'htdocs', 'cache', 'wfs')
if not os.path.exists(CACHE_DIR):
    print("ERROR - cache dir ", CACHE_DIR, " does not exist") 
    sys.exit(1)
cache_file = os.path.join(CACHE_DIR, get_file_hash(Param.WFS_URL+Param.WFS_VERSION))
if os.path.exists(cache_file):
    print("Loading pickle file")
    fp = open(cache_file, 'rb')
    WFS = pickle.load(fp)
    fp.close()
else:
    # Cache file does not exist, create WFS service and dump to file
    WFS = MyWebFeatureService(Param.WFS_URL, version=Param.WFS_VERSION, xml=None, timeout=WFS_TIMEOUT)
    print("Creating pickle file")
    fp = open(cache_file, 'wb')
    pickle.dump(WFS, fp)
    fp.close()
print("got WFS=", WFS)




def log_error(environ, msg):
    print(msg, file=environ['wsgi.errors'])

def application(environ, start_response):
    global g_BOREHOLE_DICT
    global g_BLOB_DICT
    print('application()')
    status = '200 OK'
    print("ENVIRON=", repr(environ))
    doc_root = os.path.normcase(environ['DOCUMENT_ROOT'])
    input_file_path = os.path.join(doc_root, 'input', 'NorthGawlerConvParam.json')
    sys.path.append(os.path.join(doc_root, 'lib'))
    
    if environ['PATH_INFO']=='/api/getBoreholeList':
        # TODO: 'NorthGawler' will be a URL parameter
        borehole_list = get_boreholes_list(WFS, MAX_BOREHOLES, Param)
        response_list = []
        g_BOREHOLE_DICT = {}
        g_BLOB_DICT = {}        
        for borehole_dict in borehole_list:
            borehole_id = borehole_dict['nvcl_id']
            response_list.append(borehole_id)
            g_BOREHOLE_DICT[borehole_id] = borehole_dict
        response_str = json.dumps(response_list)
        response_headers = [('Content-type', 'model/gltf+json;charset=UTF-8'), ('Content-Length', str(len(response_str))), ('Connection', 'keep-alive')]
        start_response(status, response_headers)
        return [bytes(response_str, 'utf-8')]
    
    elif environ['PATH_INFO']=='/api/getQuery':
        # Parse id from query string
        bh_id_arr = urllib.parse.parse_qs(environ['QUERY_STRING']).get('id', [])
        if len(bh_id_arr)>0:
            print("Clicked on ", bh_id_arr[0])
            # Query database
            # Open up query database
            qdb = QueryDB()
            qdb.open_db(create=False, db_name="sqlite:///"+os.path.join(doc_root, "query_data.db"))
            label, model_name, segment_str, part_str, model_str, user_str = qdb.query(bh_id_arr[0], 'model_name')
            borehole_dict = {}
            if segment_str != None:
                segment_info = json.loads(segment_str)
                borehole_dict.update(segment_info)
            if part_str != None:
                part_info = json.loads(part_str)
                borehole_dict.update(part_info)
            if model_str != None:    
                model_info = json.loads(model_str)
                borehole_dict.update(model_info)
            if user_str != None:
                user_info = json.loads(user_str) 
                borehole_dict.update(user_info)
            borehole_str = json.dumps(borehole_dict)
            borehole_bytes = bytes(borehole_str, 'utf-8')
            response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(borehole_bytes))), ('Connection', 'keep-alive')]
            start_response(status, response_headers)
            return [borehole_bytes]

    elif environ['PATH_INFO']=='/api/getBoreholeGLTF':
        
        # TEMP borehole_config, blob = get_boreholes(input_file_path) # get_boreholes_fast()
        #fp = open(os.path.join('C:', os.sep, 'users', 'vjf', 'Desktop', 'bh_config.pck'), 'wb')
        #pickle.dump(borehole_config, fp)
        #fp.close()
        
        # Parse id from query string
        bh_id_arr = urllib.parse.parse_qs(environ['QUERY_STRING']).get('id', [])
        if len(bh_id_arr)>0: 
            # Get NVCL borehole using id provided
            borehole_dict = g_BOREHOLE_DICT.get(bh_id_arr[0])
            if borehole_dict != None:
                blob = get_blob_boreholes(borehole_dict, Param)
                # Some boreholes do not have the requested metric
                if blob != None:
                    g_BLOB_DICT[bh_id_arr[0]] = blob
                    for i in range(2):
                        # GLTF file
                        if len(blob.contents.name.data) == 0:
                            # Convert to byte array
                            bcd = ctypes.cast(blob.contents.data, ctypes.POINTER(blob.contents.size * ctypes.c_char))
                            bcd_bytes = b''
                            for b in bcd.contents:
                                bcd_bytes += b
                            # Convert to json,
                            gltf_json = json.loads(bcd_bytes)
                            # Insert borehole id as a parameter so we can tell them apart
                            gltf_json["buffers"][0]["uri"] += "?id=" + bh_id_arr[0]
                            # Convert back to bytes and send
                            gltf_str = json.dumps(gltf_json)
                            gltf_bytes = bytes(gltf_str, 'utf=8')
                            response_headers = [('Content-type', 'model/gltf+json;charset=UTF-8'), ('Content-Length', str(len(gltf_bytes))), ('Connection', 'keep-alive')]
                            start_response(status, response_headers)
                            return [gltf_bytes]
                        
                        blob = blob.contents.next
            else:
                print("Cannot locate borehole in dict")
        else:
            print("Cannot locate borehole id in URL")
            
    elif environ['PATH_INFO']=='/api/$blobfile.bin':
    
        # Get the GLTF binary file associated with each GLTF file
        bh_id_arr = urllib.parse.parse_qs(environ['QUERY_STRING']).get('id', [])
        if len(bh_id_arr)>0:
            blob = g_BLOB_DICT.get(bh_id_arr[0])
            if blob != None:
                for i in range(2):
                    # Binary file (.bin)
                    if blob.contents.name.data == b'bin':
                        response_headers = [('Content-type', 'application/octet-stream'), ('Content-Length', str(blob.contents.size)), ('Connection', 'keep-alive')]
                        start_response(status, response_headers)
                        # Convert to byte array 
                        bcd = ctypes.cast(blob.contents.data, ctypes.POINTER(blob.contents.size * ctypes.c_char))
                        bcd_bytes = b''
                        for b in bcd.contents:
                            bcd_bytes += b
                        return [bcd_bytes]
                        
                    blob = blob.contents.next
            else:
                print("Cannot locate blob in dict")
        else:
            print("Cannot locate id in blobfile.bin url")

    start_response(status, [('Content-type', 'text/plain'), ('Content-Length', '1'), ('Connection', 'keep-alive')])
    print('return()')
    return [b' ']