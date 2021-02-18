import configparser
from .gpt_plugin import GPTPlugin
from .gpt_utils import printtbl, println, make_request, join_url, printlg

class Toggl(GPTPlugin):

    name = "toggl"
    url = "https://api.track.toggl.com/api/v8"
    token = None

    def __init__(self, gpt):    
        super().__init__(gpt)
    
    def setup(self):
        try:
            self.token = self.gpt.gptconfig_get(self.name, "token")
        except configparser.NoSectionError as e:
            printlg(error=e)
            self.gpt.gptconfig_set_section(self.name)
            self.add_parse_args(kind="setup-args")
        except configparser.NoOptionError as e:
            printlg(error=e)
            self.add_parse_args(kind="setup-args")
            params =  self.gpt.gptparse_params()
            self.token = params.toggl_token
            try:
                if self.auth():
                    self.gpt.gptconfig_set(self.name, "token", self.token)
                    print("Now you can use the plugin %s" % self.name)
                else: 
                    raise Exception("Fail auth")
            except Exception as e:
                printlg(critical=e)
                exit(0)

    def add_parse_args(self, kind):
        if kind == "setup-args":
            self.gpt.parse.add_argument('--toggl-token',
                action='store', 
                dest='toggl_token', 
                help=' e.g 23bc78d4e46edd5479885db4260ecsf3', 
                required=True
            )
        else:
            self.gpt.parse.add_argument('--toggl-workspaces', 
                action='store_const', 
                dest='toggl_workspaces', 
                help='List workspaces',     
                const=True,                
            )
            self.gpt.parse.add_argument('--toggl-projects', 
                action='store_const', 
                dest='toggl_projects', 
                help='List projects',     
                const=True,
            )

    http_auth = lambda self: (self.token, "api_token")

    def auth(self):
        try:
            data =  self.http_call('GET', "%s/me" % self.url, auth=self.http_auth())
            if data['data']['id']:
                return True
        except Exception as e :
            pass
        return False
    
    def cli(self):
        params = self.gpt.gptparse_params()

        def findbyid(rows, id):
            for row in rows:
                for k in row.keys():
                    if k == 'id' and str(row.get(k)) == id:
                        return row
            return None

        def onlycolumns(rows):
            l = []
            for r in rows: 
                l.append( { 'id': r.get('id'), 'name':  r.get('name')})
            return l

        if params.toggl_workspaces:
            try:
                rows = self.workspaces()
                if rows:
                    rows = onlycolumns(rows)
                    if params.set:
                        row = findbyid(rows, params.set)
                        if row:
                            self.gpt.gptconfig_set(self.name, "workspace_id",row.get('id') )
                            self.gpt.gptconfig_set(self.name, "workspace_name",row.get('name') )

                            self.gpt.gptconfig_set(self.name, "project_id", "")
                            self.gpt.gptconfig_set(self.name, "project_name","" )

                            printtbl([row])
                        else:
                            println('The workspace ID was not found')
                    else:
                        printtbl(rows)
                else:
                    raise Exception("Fail to get workspaces")
            except Exception as e:
                printlg(exception=e)
        elif params.toggl_projects:
            try:
                workspace_id = self.gpt.gptconfig_get(self.name, "workspace_id")
            except Exception as e:
                workspace = self.workspaces(filter='first')
                workspace_id = workspace.get('id')
            try:
                rows = self.projects(workspace_id)
                if rows:
                    rows = onlycolumns(rows)
                    if params.set:
                        row = findbyid(rows, params.set)
                        if row: 
                            self.gpt.gptconfig_set(self.name, "project_id",row.get('id') )
                            self.gpt.gptconfig_set(self.name, "project_name",row.get('name') )
                            printtbl([row])
                        else:
                            println('The project ID was not found')
                    else: 
                        printtbl(rows)
                else:
                    raise Exception("Fail to get projects")
            except Exception as e:
                printlg(exception=e)
   
    def workspaces(self, filter=""):
        url = join_url(self.url, "workspaces")
        try:
            data = make_request('GET', url, auth=self.http_auth())
            if filter =='first':            
                return len(data) and data[0]
            return data
        except:
            pass
        return None

    def projects(self, workspace_id, filter=""):
        try:
            url = join_url(self.url, "workspaces/{}/projects".format(workspace_id))
            data = make_request('GET',url, auth=self.http_auth())
            if filter =='first' :
                    return len(data) and data[0]
            return data
        except :
            pass
        return None
    
    def add_time_entry(self, **kwargs):        
        description = kwargs.get('name')
        start= kwargs.get('start')
        end= kwargs.get('end')
        minutes = kwargs.get('minutes')
        
        workspace_id  = None
        try:
            workspace_id = self.gpt.gptconfig_get(self.name, "workspace_id")
        except Exception as e:
            try:
                workspace, err = self.workspaces(filter='first')
                workspace_id = workspace.get('id')
            except Exception as e:
                pass
        
        project_id = None
        try:
            project_id = self.gpt.gptconfig_get(self.name, "project_id")
        except Exception as e:
            pass
        
        time_entry = {
            "start": start, # Required 
            "description": description,
            "projectId": project_id,
            "stop": end, # Required
            "duration": float(minutes) * 60,
            "created_with": "gp-tracking"
        }

        if workspace_id:
            time_entry.update({'wid': workspace_id})

        if project_id:
            time_entry.update({'pid': project_id})
        
        try:
            url = join_url(self.url, "time_entries")
            data = make_request(
                'POST',url, auth= self.http_auth(),
                json= {"time_entry": time_entry}
            )
            return data["data"]["id"]
        except Exception as e:
            printlg(exception=e)
        return -1
    
    def status(self):
        items = []
        def getstate(param):
            try:
                id = self.gpt.gptconfig_get(self.name, param+"_id")
                name =self.gpt.gptconfig_get(self.name, param+"_name")
                if len(id) and len(name):
                    items.append({
                        'key': str(param).title(),
                        'value': "%s  %s" % ( id, name)
                        })
            except:
                pass
        getstate('workspace')
        getstate('project')
        printtbl(items)