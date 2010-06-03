%if len(task_order) > 0:
<div class="status"> <em>Tasklist:</em> <ul>
%for m_name,task in task_order:
% ti = None
%if 'active_instance' in task_updates[m_name][task]: ti = task_updates[m_name][task]['active_instance']
{{task_updates[m_name][task]}}
%if 'error' in task_updates[m_name][task]:
<li class="error">Model <a href="/models/{{m_name}}">{{m_name}}</a> - Instance {{ti}} - Task: {{task}} - <span class="error">ERROR: {{task_updates[m_name][task]['error']}}</span>. If you keep getting this, email <a href="mailto:mdig-users@googlegroups.com">mdig-users@googlegroups.com</a>
%elif 'complete' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Instance {{ti}} - Task: {{task}} - Completed at: {{task_updates[m_name][task]['complete']}}
%elif 'percent_complete' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Instance {{ti}} - Task: {{task}} - Percent complete: {{task_updates[m_name][task]['percent_complete']}}%.
%elif 'active' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Instance {{ti}} - Task: {{task}} - Active.
%elif 'started' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Instance {{ti}} - Task: {{task}} - Started at {{task_updates[m_name][task]['started']}}
%else:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Instance {{ti}} - Task: {{task}} - In queue.
%end
%if 'status' in task_updates[m_name][task]: 
 Status: {{task_updates[m_name][task]['status']}}
%end
</li>
%end
</ul>
</div>
%end
