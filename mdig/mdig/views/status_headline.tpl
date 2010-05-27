%if len(task_order) > 0:
<div class="status"> <em>Tasklist:</em> <ul>
%for m_name,task in task_order:
%if 'error' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - ERROR: {{task_updates[m_name][task]['error']}}. If you keep getting this, email <a href="mailto:mdig-users@googlegroups.com">mdig-users@googlegroups.com</a>
%elif 'complete' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Completed at: {{task_updates[m_name][task]['complete']}}
%elif 'percent_complete' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Instance {{task_updates[m_name][task]['active'][0]}} - Percent complete: {{task_updates[m_name][task]['percent_complete']}}%.
%elif 'active' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Instance {{task_updates[m_name][task]['active']}} active.
%elif 'started' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Started at {{task_updates[m_name][task]['started']}}
%else:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - In queue.
%end
%if 'status' in task_updates[m_name][task]: 
 Status: {{task_updates[m_name][task]['status']}}
%end
</li>
%end
</ul>
</div>
%end
