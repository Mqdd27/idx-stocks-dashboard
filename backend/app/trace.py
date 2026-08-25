import time
from collections import Counter
from langchain_core.callbacks import BaseCallbackHandler

class Trace(BaseCallbackHandler):
    def __init__(self):
        self.started=time.monotonic(); self.llms=[]; self.tools=[]; self.nodes=[]
    def _out(self, kind, name, elapsed=None, extra=''):
        print(f'TRACE {kind} name={name} elapsed={elapsed if elapsed is not None else ""} {extra}', flush=True)
    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs):
        self.llms.append([run_id,time.monotonic(),serialized.get('name') or serialized.get('id'),parent_run_id])
        self._out('LLM_START', self.llms[-1][2], extra=f'count={len(self.llms)}')
    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        for r in self.llms:
            if r[0]==run_id and len(r)<5:
                r.append(time.monotonic()); r.append(response); self._out('LLM_END',r[2],round(r[4]-r[1],2)); break
    def on_llm_error(self,error,*,run_id, parent_run_id=None, **kwargs): self._out('LLM_ERROR',str(error)[:160])
    def on_tool_start(self, serialized,input_str,*,run_id,parent_run_id=None,**kwargs):
        name=serialized.get('name') or serialized.get('id') or 'unknown'; self.tools.append([name,time.monotonic(),input_str]); self._out('TOOL_START',name,extra=f'count={len(self.tools)} args={str(input_str)[:120]}')
    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs): self._out('TOOL_END','tool',extra=f'output={str(output)[:100]}')
    def summary(self):
        return {'elapsed':round(time.monotonic()-self.started,2),'llms':len(self.llms),'tools':len(self.tools),'tool_counts':Counter(x[0] for x in self.tools)}

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        name = serialized.get('name') or str(serialized.get('id', ['chain'])[-1])
        self.nodes.append([run_id, name, time.monotonic()])
        self._out('NODE_START', name, extra=f'step={len(self.nodes)}')
    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        for row in reversed(self.nodes):
            if row[0] == run_id and len(row) == 3:
                row.append(time.monotonic()); self._out('NODE_END', row[1], round(row[3]-row[2], 2)); break
