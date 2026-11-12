'use strict';
// Course-extension navigation. Existing course data and original menus are preserved.
const vehicleOriginalNavigation=renderNavigation;
renderNavigation=function(){vehicleOriginalNavigation();if(activeCourse!=='design')return;const nav=document.querySelector('#nav');if(!nav.querySelector('[data-page="vehicle"]')){const button=document.createElement('button');button.dataset.page='vehicle';button.textContent='◈　无人车竞赛';nav.append(button)}};
views.vehicle=async()=>({html:heading('无人车竞赛','GP-MPC 教师基准 · 独立沙箱 · 双车可视化回放')+'<iframe title="无人车竞赛工作台" src="/courses/design/vehicle/" style="width:100%;height:1450px;border:0;border-radius:14px;background:#f2f5f3" referrerpolicy="same-origin"></iframe>'});
if(user)renderNavigation();
