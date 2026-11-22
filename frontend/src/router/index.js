import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import LoginView from '../views/LoginView.vue'
import { getAuthStatus } from '../api/auth'
import { authState, safeRedirect } from '../utils/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView
  },
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 查询一次后端是否开启登录；后端暂时不可用时放行，等下次导航再查
const ensureAuthStatus = async () => {
  if (authState.checked) return
  try {
    const res = await getAuthStatus()
    authState.enabled = !!res.data?.enabled
    authState.authenticated = !!res.data?.authenticated
    authState.checked = true
  } catch (error) {
    console.error('Failed to check login status:', error)
  }
}

router.beforeEach(async (to) => {
  await ensureAuthStatus()
  const loginRequired = authState.enabled && !authState.authenticated

  if (to.name === 'Login') {
    return loginRequired ? true : { path: safeRedirect(to.query.redirect) }
  }
  if (loginRequired) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
