<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type Report, type Resource, type SearchResult, type User } from './api'

const token = ref(localStorage.getItem('access_token'))
const user = ref<User>()
const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const displayName = ref('')
const code = ref('')
const query = ref('')
const resources = ref<Resource[]>([])
const results = ref<SearchResult[]>([])
const agentAnswer = ref('')
const loading = ref(false)
const uploadOpen = ref(false)
const showMine = ref(false)
const adminOpen = ref(false)
const reports = ref<Report[]>([])
const file = ref<File>()
const copyrightConfirmed = ref(false)
const form = ref({ title: '', description: '', experience: '', course: '', category: '', tags: '' })

const statusLabels: Record<Resource['status'], string> = {
  processing: '解析中',
  waiting_confirmation: '待确认',
  published: '已发布',
  failed: '解析失败',
  hidden: '已下架',
}

const shownResources = computed(() => results.value.length ? results.value.map(item => item.resource) : resources.value)

async function requestCode() {
  await api.post('/auth/register-code', { email: email.value })
  ElMessage.success('验证码已发送；开发模式请查看 API 日志或 Mailpit')
}

async function authenticate() {
  try {
    const path = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const body = mode.value === 'login'
      ? { email: email.value, password: password.value }
      : { email: email.value, password: password.value, code: code.value, display_name: displayName.value }
    const { data } = await api.post(path, body)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    token.value = data.access_token
    await loadMe()
    await loadResources()
  } catch (error: any) {
    showError(error)
  }
}

function logout() {
  localStorage.clear()
  token.value = null
}

function showError(error: any) {
  ElMessage.error(error.response?.data?.error?.message || error.response?.data?.detail || '操作失败')
}

async function loadMe() {
  const { data } = await api.get<User>('/auth/me')
  user.value = data
}

async function loadResources(mine = showMine.value) {
  adminOpen.value = false
  showMine.value = mine
  const { data } = await api.get<Resource[]>('/resources', { params: { mine } })
  resources.value = data
  results.value = []
}

async function search() {
  if (!query.value.trim()) return loadResources()
  loading.value = true
  try {
    const { data } = await api.get<SearchResult[]>('/search', { params: { q: query.value } })
    results.value = data
    agentAnswer.value = ''
  } catch (error: any) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function askAgent() {
  if (!query.value.trim()) return
  loading.value = true
  try {
    const { data } = await api.post('/agent/chat', { message: query.value })
    results.value = data.resources
    agentAnswer.value = data.answer
  } catch (error: any) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function upload() {
  if (!file.value || !form.value.title) return ElMessage.warning('请填写标题并选择文件')
  if (!copyrightConfirmed.value) return ElMessage.warning('请确认你有权分享该资料')
  const data = new FormData()
  Object.entries(form.value).forEach(([key, value]) => data.append(key, value))
  data.append('rights_confirmed', String(copyrightConfirmed.value))
  data.append('file', file.value)
  loading.value = true
  try {
    await api.post('/resources', data)
    ElMessage.success('上传成功，资料正在解析')
    uploadOpen.value = false
    await loadResources(true)
  } catch (error: any) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function confirm(item: Resource) {
  try {
    await api.post(`/resources/${item.id}/confirm`)
    ElMessage.success('资料已发布')
    await loadResources(true)
  } catch (error: any) { showError(error) }
}

async function download(item: Resource) {
  const { data } = await api.post(`/resources/${item.id}/download-ticket`)
  window.location.href = data.url
}

async function reportResource(item: Resource) {
  const reason = window.prompt('举报原因（例如：版权问题、内容不实）')
  if (!reason) return
  try {
    await api.post('/reports', { resource_id: item.id, reason, details: '' })
    ElMessage.success('举报已提交，管理员会进行审核')
  } catch (error: any) { showError(error) }
}

async function loadReports() {
  try {
    const { data } = await api.get<Report[]>('/admin/reports')
    reports.value = data
    adminOpen.value = true
  } catch (error: any) { showError(error) }
}

async function resolveReport(item: Report, status: 'resolved' | 'rejected') {
  const resolution = window.prompt('填写处理说明')
  if (!resolution) return
  await api.patch(`/admin/reports/${item.id}`, { status, resolution })
  await loadReports()
}

async function hideResource(resourceId: string) {
  await api.post(`/admin/resources/${resourceId}/hide`)
  ElMessage.success('资源已下架')
  await loadReports()
}

onMounted(async () => { if (token.value) { await loadMe(); await loadResources() } })
</script>

<template>
  <main v-if="!token" class="auth-shell">
    <section class="brand-panel">
      <span class="eyebrow">CAMPUS KNOWLEDGE COMMONS</span>
      <h1>拾页</h1>
      <p>让散落在同学电脑里的好资料，被真正需要的人找到。</p>
    </section>
    <section class="auth-card">
      <h2>{{ mode === 'login' ? '欢迎回来' : '加入校园资料库' }}</h2>
      <el-input v-model="email" size="large" placeholder="校内邮箱" />
      <el-input v-if="mode === 'register'" v-model="displayName" size="large" placeholder="昵称" />
      <div v-if="mode === 'register'" class="code-row">
        <el-input v-model="code" size="large" placeholder="6 位验证码" />
        <el-button size="large" @click="requestCode">获取验证码</el-button>
      </div>
      <el-input v-model="password" size="large" type="password" show-password placeholder="密码（至少 8 位）" />
      <el-button type="primary" size="large" @click="authenticate">
        {{ mode === 'login' ? '登录' : '注册并登录' }}
      </el-button>
      <button class="text-button" @click="mode = mode === 'login' ? 'register' : 'login'">
        {{ mode === 'login' ? '没有账号？使用校内邮箱注册' : '已有账号？返回登录' }}
      </button>
    </section>
  </main>

  <div v-else class="app-shell">
    <header>
      <a class="logo" href="#">拾页 <small>NWU 资源中心</small></a>
      <nav><button @click="loadResources(false)">资源广场</button><button @click="loadResources(true)">我的分享</button><button @click="uploadOpen = true">分享资料</button><button v-if="user?.is_admin" @click="loadReports">审核台</button><button @click="logout">退出</button></nav>
    </header>
    <section class="hero">
      <span class="eyebrow">SEARCH WITH CONTEXT</span>
      <h1>你想找什么资料？</h1>
      <p>描述课程、用途或遇到的问题，AI 会从校内同学分享的内容中寻找答案。</p>
      <div class="search-box">
        <input v-model="query" @keyup.enter="askAgent" placeholder="例如：帮我找适合期末突击的高数重点笔记" />
        <button @click="search">普通搜索</button>
        <button class="primary" @click="askAgent">问 AI</button>
      </div>
      <div v-if="agentAnswer" class="agent-answer"><strong>拾页助手</strong><p>{{ agentAnswer }}</p></div>
    </section>
    <section v-if="!adminOpen" class="content">
      <div class="section-title"><div><span class="eyebrow">SHARED BY STUDENTS</span><h2>{{ showMine ? '我的分享' : '最新资料' }}</h2></div><span>{{ shownResources.length }} 项结果</span></div>
      <div v-loading="loading" class="resource-grid">
        <article v-for="item in shownResources" :key="item.id" class="resource-card">
          <div class="card-top"><span class="file-type">{{ item.original_filename.split('.').pop()?.toUpperCase() }}</span><span>{{ item.course || '通用资料' }}</span></div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.ai_summary || item.description || '等待上传者补充简介' }}</p>
          <div class="tags"><span v-for="tag in item.tags.split(',').filter(Boolean)" :key="tag">{{ tag }}</span></div>
          <blockquote v-if="item.experience">“{{ item.experience }}”</blockquote>
          <p v-if="item.status === 'failed' && item.failure_reason" class="failure-reason">失败原因：{{ item.failure_reason }}</p>
          <div class="card-actions">
            <button v-if="item.status === 'waiting_confirmation'" @click="confirm(item)">确认发布</button>
            <span v-else-if="item.status !== 'published'">{{ statusLabels[item.status] }}</span>
            <button v-else @click="download(item)">下载资料 →</button>
            <button v-if="item.status === 'published' && item.owner_id !== user?.id" class="report-button" @click="reportResource(item)">举报</button>
          </div>
        </article>
        <div v-if="!shownResources.length" class="empty">还没有匹配的资料，成为第一位分享者吧。</div>
      </div>
    </section>
    <section v-else class="content">
      <div class="section-title"><div><span class="eyebrow">MODERATION</span><h2>举报审核台</h2></div><span>{{ reports.length }} 条举报</span></div>
      <div class="report-list">
        <article v-for="item in reports" :key="item.id" class="report-row">
          <div><strong>{{ item.reason }}</strong><p>{{ item.details || '未补充说明' }}</p><small>资源 {{ item.resource_id }} · {{ item.status }}</small></div>
          <div v-if="item.status === 'pending'" class="report-actions"><button @click="hideResource(item.resource_id)">下架资源</button><button @click="resolveReport(item, 'resolved')">标记已处理</button><button @click="resolveReport(item, 'rejected')">驳回</button></div>
        </article>
      </div>
    </section>
  </div>

  <el-dialog v-model="uploadOpen" title="分享一份资料" width="min(560px, 92vw)">
    <el-form label-position="top">
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <div class="form-grid"><el-form-item label="课程"><el-input v-model="form.course" /></el-form-item><el-form-item label="分类"><el-input v-model="form.category" /></el-form-item></div>
      <el-form-item label="资料简介"><el-input v-model="form.description" type="textarea" /></el-form-item>
      <el-form-item label="使用经验"><el-input v-model="form.experience" type="textarea" placeholder="它适合什么时候用？哪些部分最有帮助？" /></el-form-item>
      <el-form-item label="标签"><el-input v-model="form.tags" placeholder="期末, 高数, 重点笔记" /></el-form-item>
      <el-form-item label="文件"><input type="file" accept=".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg" @change="file = ($event.target as HTMLInputElement).files?.[0]" /></el-form-item>
      <el-checkbox v-model="copyrightConfirmed">我确认拥有分享权限，且资料不包含违法、侵权或敏感内容</el-checkbox>
    </el-form>
    <template #footer><el-button @click="uploadOpen = false">取消</el-button><el-button type="primary" :loading="loading" @click="upload">上传并解析</el-button></template>
  </el-dialog>
</template>
