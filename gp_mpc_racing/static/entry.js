'use strict';
// Course-extension navigation. Existing course data and original menus are preserved.
const vehicleOriginalNavigation=renderNavigation;
renderNavigation=function(){vehicleOriginalNavigation();if(activeCourse!=='design')return;const nav=document.querySelector('#nav');if(!nav.querySelector('[data-page="vehicle"]')){const button=document.createElement('button');button.dataset.page='vehicle';button.textContent='◈　无人车竞赛';nav.append(button)}};
views.vehicle=async()=>({html:heading('无人车竞赛','原MATLAB程序保留 · 原Track02 · 双车回放与独立移植赛制')+'<iframe title="无人车竞赛工作台" src="/courses/design/vehicle/" style="width:100%;height:1450px;border:0;border-radius:14px;background:#f2f5f3" referrerpolicy="same-origin"></iframe>'});
if(user)renderNavigation();
