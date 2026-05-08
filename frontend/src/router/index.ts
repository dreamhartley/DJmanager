import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/work/:rjCode',
      name: 'work-detail',
      component: () => import('../views/WorkDetail.vue'),
      props: true,
    },
  ],
})

export default router
