<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, type Engagement, type HelpRequest, type Report, type Resource, type ResourceComment, type SearchResult, type User, type UserProfile } from './api'

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
const helpCenterOpen = ref(false)
const helpDialogOpen = ref(false)
const guideOpen = ref(false)
const profile = ref<UserProfile>()
const profileOwnerId = ref<string>()
const helpRequests = ref<HelpRequest[]>([])
const helpQuery = ref('')
const helpSort = ref<'hot' | 'newest'>('hot')
const helpForm = ref({ title: '', description: '', college: '通用', major: '通用', course: '通用' })
const reports = ref<Report[]>([])
const comments = ref<ResourceComment[]>([])
const commentResource = ref<Resource>()
const commentContent = ref('')
const commentsOpen = ref(false)
const previewKind = ref<'pdf' | 'image' | 'text'>('text')
const previewUrl = ref('')
const previewText = ref('')
const previewTruncated = ref(false)
const previewLoading = ref(false)
const file = ref<File>()
const copyrightConfirmed = ref(false)
const resourceTypes = ['电子课本', '课堂课件', '个人笔记', '经验分享', '其他']
const filters = ref({ resource_type: '', college: '', major: '', course: '', teacher: '', grade: '', year: '', sort_by: 'newest' })
const form = ref({
  title: '', resource_type: '', college: '通用', major: '通用', course: '通用',
  teacher: '通用', grade: '通用', year: new Date().getFullYear(), description: '',
  experience: '', category: '', tags: '', is_anonymous: false,
})

const statusLabels: Record<Resource['status'], string> = {
  processing: '解析中',
  waiting_confirmation: '待确认',
  published: '已发布',
  failed: '解析失败',
  hidden: '已下架',
}

const shownResources = computed(() => results.value.length ? results.value.map(item => item.resource) : resources.value)
const profileLikes = computed(() => shownResources.value.reduce((sum, item) => sum + item.like_count, 0))

async function requestCode() {
  if (!email.value.trim()) return ElMessage.warning('请先填写校内邮箱')
  try {
    await api.post('/auth/register-code', { email: email.value })
    ElMessage.success('验证码已发送；开发模式请查看 API 日志或 Mailpit')
  } catch (error: any) {
    showError(error)
  }
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
  guideOpen.value = !data.onboarding_completed
}

function activeFilters() {
  return Object.fromEntries(Object.entries(filters.value).filter(([, value]) => value !== ''))
}

async function loadResources(mine = showMine.value, ownerId?: string) {
  adminOpen.value = false
  helpCenterOpen.value = false
  showMine.value = mine
  profileOwnerId.value = ownerId
  if (!mine && !ownerId) profile.value = undefined
  const { data } = await api.get<Resource[]>('/resources', {
    params: { mine, owner_id: ownerId, q: query.value.trim() || undefined, ...activeFilters() },
  })
  resources.value = data
  results.value = []
}

async function openMyProfile() {
  if (!user.value) return
  const { data } = await api.get<UserProfile>(`/users/${user.value.id}`)
  profile.value = data
  await loadResources(true)
}

async function openUserProfile(item: Resource) {
  if (item.is_anonymous) return ElMessage.info('该资料由匿名同学分享')
  commentsOpen.value = false
  const { data } = await api.get<UserProfile>(`/users/${item.owner_id}`)
  profile.value = data
  await loadResources(false, item.owner_id)
}

async function search() {
  if (!query.value.trim()) return loadResources()
  if (showMine.value || profileOwnerId.value) return loadResources(showMine.value, profileOwnerId.value)
  loading.value = true
  try {
    const { data } = await api.get<SearchResult[]>('/search', {
      params: { q: query.value, ...activeFilters() },
    })
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
  if (!form.value.resource_type) return ElMessage.warning('请选择资源类型')
  if (!copyrightConfirmed.value) return ElMessage.warning('请确认你有权分享该资料')
  const data = new FormData()
  Object.entries(form.value).forEach(([key, value]) => data.append(key, String(value)))
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

async function toggleLike(item: Resource) {
  try {
    const { data } = await api.request<Engagement>({
      url: `/resources/${item.id}/likes`,
      method: item.liked_by_me ? 'delete' : 'post',
    })
    item.liked_by_me = data.liked_by_me
    item.disliked_by_me = data.disliked_by_me
    item.like_count = data.like_count
    item.dislike_count = data.dislike_count
  } catch (error: any) { showError(error) }
}

async function toggleDislike(item: Resource) {
  try {
    const { data } = await api.request<Engagement>({
      url: `/resources/${item.id}/dislikes`,
      method: item.disliked_by_me ? 'delete' : 'post',
    })
    item.liked_by_me = data.liked_by_me
    item.disliked_by_me = data.disliked_by_me
    item.like_count = data.like_count
    item.dislike_count = data.dislike_count
  } catch (error: any) { showError(error) }
}

async function deleteResource(item: Resource) {
  try {
    await ElMessageBox.confirm(`确定删除“${item.title}”吗？文件和评论都会一并删除。`, '删除资料', { type: 'warning' })
    await api.delete(`/resources/${item.id}`)
    ElMessage.success('资料已删除')
    await loadResources(true)
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') showError(error)
  }
}

async function finishGuide() {
  const { data } = await api.patch<User>('/users/me/onboarding')
  user.value = data
  guideOpen.value = false
}

async function loadHelpRequests() {
  adminOpen.value = false
  helpCenterOpen.value = true
  const { data } = await api.get<HelpRequest[]>('/help-requests', {
    params: { q: helpQuery.value || undefined, sort_by: helpSort.value },
  })
  helpRequests.value = data
}

async function createHelpRequest() {
  try {
    await api.post('/help-requests', helpForm.value)
    helpDialogOpen.value = false
    helpForm.value = { title: '', description: '', college: '通用', major: '通用', course: '通用' }
    ElMessage.success('求助已发布')
    await loadHelpRequests()
  } catch (error: any) { showError(error) }
}

async function toggleHelpSupport(item: HelpRequest) {
  const { data } = await api.request<{ supported_by_me: boolean, heat_count: number }>({
    url: `/help-requests/${item.id}/supports`,
    method: item.supported_by_me ? 'delete' : 'post',
  })
  item.supported_by_me = data.supported_by_me
  item.heat_count = data.heat_count
}

function revokePreviewUrl() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

async function openResourcePreview(item: Resource) {
  revokePreviewUrl()
  commentResource.value = item
  commentsOpen.value = true
  previewLoading.value = true
  previewText.value = ''
  previewTruncated.value = false
  try {
    const commentsRequest = api.get<ResourceComment[]>(`/resources/${item.id}/comments`)
    if (item.content_type === 'application/pdf' || item.content_type.startsWith('image/')) {
      const [commentsResponse, previewResponse] = await Promise.all([
        commentsRequest,
        api.get(`/resources/${item.id}/preview`, { responseType: 'blob' }),
      ])
      comments.value = commentsResponse.data
      previewKind.value = item.content_type === 'application/pdf' ? 'pdf' : 'image'
      previewUrl.value = URL.createObjectURL(previewResponse.data)
    } else {
      const [commentsResponse, previewResponse] = await Promise.all([
        commentsRequest,
        api.get<{ text: string, truncated: boolean }>(`/resources/${item.id}/preview-text`),
      ])
      comments.value = commentsResponse.data
      previewKind.value = 'text'
      previewText.value = previewResponse.data.text
      previewTruncated.value = previewResponse.data.truncated
    }
    commentContent.value = ''
  } catch (error: any) { showError(error) }
  finally { previewLoading.value = false }
}

async function submitComment() {
  const resource = commentResource.value
  const content = commentContent.value.trim()
  if (!resource || !content) return ElMessage.warning('请输入评论内容')
  try {
    const { data } = await api.post<ResourceComment>(`/resources/${resource.id}/comments`, { content })
    comments.value.push(data)
    resource.comment_count += 1
    commentContent.value = ''
  } catch (error: any) { showError(error) }
}

async function deleteComment(item: ResourceComment) {
  const resource = commentResource.value
  if (!resource) return
  try {
    await api.delete(`/resources/${resource.id}/comments/${item.id}`)
    comments.value = comments.value.filter(comment => comment.id !== item.id)
    resource.comment_count = Math.max(0, resource.comment_count - 1)
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
    helpCenterOpen.value = false
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

watch(commentsOpen, (open) => { if (!open) revokePreviewUrl() })
onUnmounted(revokePreviewUrl)
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
      <nav><button @click="loadResources(false)">资源广场</button><button @click="openMyProfile">我的主页</button><button @click="loadHelpRequests">资源求助</button><button @click="uploadOpen = true">分享资料</button><button v-if="user?.is_admin" @click="loadReports">审核台</button><button @click="logout">退出</button></nav>
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
    <section v-if="!adminOpen && !helpCenterOpen" class="content page-view">
      <div v-if="showMine || profileOwnerId" class="profile-header">
        <div class="avatar large">{{ (profile?.display_name || user?.display_name || '?').slice(0, 1).toUpperCase() }}</div>
        <div><span class="eyebrow">CAMPUS PROFILE</span><h2>{{ showMine ? '我的主页' : `${profile?.display_name || '同学'}的主页` }}</h2><p>{{ shownResources.length }} 份资料 · 共获 {{ profile?.total_likes ?? profileLikes }} 个赞</p></div>
      </div>
      <div class="filter-panel">
        <el-select v-model="filters.resource_type" clearable placeholder="资源类型"><el-option v-for="item in resourceTypes" :key="item" :label="item" :value="item" /></el-select>
        <el-input v-model="filters.college" clearable placeholder="学院" />
        <el-input v-model="filters.major" clearable placeholder="专业" />
        <el-input v-model="filters.course" clearable placeholder="课程" />
        <el-input v-model="filters.teacher" clearable placeholder="课程老师" />
        <el-input v-model="filters.grade" clearable placeholder="年级" />
        <el-input v-model="filters.year" clearable placeholder="年份" />
        <el-select v-model="filters.sort_by"><el-option label="最新上传" value="newest" /><el-option label="点赞最多" value="likes" /></el-select>
        <el-button type="primary" @click="loadResources(showMine, profileOwnerId)">应用筛选</el-button>
      </div>
      <div class="section-title"><div><span class="eyebrow">SHARED BY STUDENTS</span><h2>{{ showMine ? '我的资料' : profileOwnerId ? '公开分享' : '最新资料' }}</h2></div><span>{{ shownResources.length }} 项结果</span></div>
      <div v-loading="loading" class="resource-grid">
        <article v-for="item in shownResources" :key="item.id" class="resource-card">
          <div class="card-top"><span class="file-type">{{ item.resource_type }} · {{ item.original_filename.split('.').pop()?.toUpperCase() }}</span><span>{{ item.course || '通用资料' }}</span></div>
          <h3>{{ item.title }}</h3>
          <div class="resource-byline"><button v-if="!item.is_anonymous" @click="openUserProfile(item)"><span class="avatar">{{ item.owner_name.slice(0, 1).toUpperCase() }}</span>{{ item.owner_name }}</button><span v-else>匿名同学</span><time>{{ new Date(item.created_at).toLocaleDateString() }}</time></div>
          <small class="resource-scope">{{ item.college }} · {{ item.major }} · {{ item.grade }} · {{ item.teacher }} · {{ item.year || '不限年份' }}</small>
          <p>{{ item.ai_summary || item.description || '等待上传者补充简介' }}</p>
          <div class="tags"><span v-for="tag in item.tags.split(',').filter(Boolean)" :key="tag">{{ tag }}</span></div>
          <blockquote v-if="item.experience">“{{ item.experience }}”</blockquote>
          <p v-if="item.status === 'failed' && item.failure_reason" class="failure-reason">失败原因：{{ item.failure_reason }}</p>
          <div v-if="item.status === 'published'" class="engagement-actions">
            <button :class="{ liked: item.liked_by_me }" @click="toggleLike(item)">♥ {{ item.like_count }}</button>
            <button :class="{ disliked: item.disliked_by_me }" @click="toggleDislike(item)">踩 {{ item.dislike_count }}</button>
            <button @click="openResourcePreview(item)">评论 {{ item.comment_count }}</button>
          </div>
          <div class="card-actions">
            <button v-if="item.status === 'waiting_confirmation'" @click="confirm(item)">确认发布</button>
            <span v-else-if="item.status !== 'published'">{{ statusLabels[item.status] }}</span>
            <button v-else @click="openResourcePreview(item)">预览资料 →</button>
            <button v-if="item.status === 'published' && item.owner_id !== user?.id" class="report-button" @click="reportResource(item)">举报</button>
            <button v-if="item.owner_id === user?.id" class="danger-button" @click="deleteResource(item)">删除</button>
          </div>
        </article>
        <div v-if="!shownResources.length" class="empty">还没有匹配的资料，成为第一位分享者吧。</div>
      </div>
    </section>
    <section v-else-if="helpCenterOpen" class="content page-view">
      <div class="section-title"><div><span class="eyebrow">RESOURCE WISHLIST</span><h2>资源求助中心</h2></div><el-button type="primary" @click="helpDialogOpen = true">发布求助</el-button></div>
      <div class="help-search"><el-input v-model="helpQuery" clearable placeholder="搜索课程或资料名称" @keyup.enter="loadHelpRequests" /><el-select v-model="helpSort" @change="loadHelpRequests"><el-option label="热度榜" value="hot" /><el-option label="最新发布" value="newest" /></el-select><el-button @click="loadHelpRequests">搜索</el-button></div>
      <div class="help-list">
        <article v-for="item in helpRequests" :key="item.id" class="help-card">
          <button :class="{ active: item.supported_by_me }" class="heat-button" @click="toggleHelpSupport(item)"><strong>{{ item.heat_count }}</strong><span>{{ item.supported_by_me ? '已同求' : '同求' }}</span></button>
          <div><div class="help-meta">{{ item.college }} · {{ item.major }} · {{ item.course }} · {{ new Date(item.created_at).toLocaleString() }}</div><h3>{{ item.title }}</h3><p>{{ item.description || '未补充详细说明' }}</p><small>发布者 {{ item.author_name }} · ID {{ item.author_id }}</small></div>
        </article>
        <div v-if="!helpRequests.length" class="empty">暂时没有匹配的求助。</div>
      </div>
    </section>
    <section v-else class="content page-view">
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
      <el-form-item label="资源类型（必填）"><el-select v-model="form.resource_type" placeholder="请选择"><el-option v-for="item in resourceTypes" :key="item" :label="item" :value="item" /></el-select></el-form-item>
      <div class="form-grid"><el-form-item label="学院"><el-input v-model="form.college" /></el-form-item><el-form-item label="专业"><el-input v-model="form.major" /></el-form-item></div>
      <div class="form-grid"><el-form-item label="课程"><el-input v-model="form.course" /></el-form-item><el-form-item label="课程老师"><el-input v-model="form.teacher" placeholder="可填姓名或缩写" /></el-form-item></div>
      <div class="form-grid"><el-form-item label="年级"><el-input v-model="form.grade" /></el-form-item><el-form-item label="年份"><el-input-number v-model="form.year" :min="1900" :max="2200" /></el-form-item></div>
      <el-form-item label="资料简介"><el-input v-model="form.description" type="textarea" /></el-form-item>
      <el-form-item label="使用经验"><el-input v-model="form.experience" type="textarea" placeholder="它适合什么时候用？哪些部分最有帮助？" /></el-form-item>
      <el-form-item label="标签"><el-input v-model="form.tags" placeholder="期末, 高数, 重点笔记" /></el-form-item>
      <el-form-item label="文件"><input type="file" accept=".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg" @change="file = ($event.target as HTMLInputElement).files?.[0]" /></el-form-item>
      <p class="upload-note">最大允许 200 MB；超过 50 MB 的大文件仍可分享，但将跳过 AI 内容解析。</p>
      <el-checkbox v-model="form.is_anonymous">匿名分享（资源广场不展示我的主页）</el-checkbox>
      <el-checkbox v-model="copyrightConfirmed">我确认拥有分享权限，且资料不包含违法、侵权或敏感内容</el-checkbox>
    </el-form>
    <template #footer><el-button @click="uploadOpen = false">取消</el-button><el-button type="primary" :loading="loading" @click="upload">上传并解析</el-button></template>
  </el-dialog>

  <el-dialog v-model="commentsOpen" :title="commentResource?.title || '资料预览'" width="min(1180px, 96vw)" top="4vh">
    <div class="preview-layout">
      <section class="preview-pane" v-loading="previewLoading">
        <div class="preview-meta">
          <span>{{ commentResource?.original_filename }} · <button v-if="commentResource && !commentResource.is_anonymous" @click="openUserProfile(commentResource)">{{ commentResource.owner_name }}的主页</button><em v-else>匿名分享</em></span>
          <small>{{ commentResource ? (commentResource.size_bytes / 1024 / 1024).toFixed(2) : 0 }} MB</small>
        </div>
        <iframe v-if="!previewLoading && previewKind === 'pdf' && previewUrl" :src="previewUrl" title="PDF 预览" />
        <img v-else-if="!previewLoading && previewKind === 'image' && previewUrl" :src="previewUrl" alt="资料图片预览" />
        <div v-else-if="!previewLoading && previewKind === 'text'" class="text-preview">
          <pre>{{ previewText || '该资料暂未提取到可预览文本。' }}</pre>
          <small v-if="previewTruncated">预览内容较长，仅展示前 40000 个字符。</small>
        </div>
      </section>
      <aside class="comments-pane">
        <h3>评论区 <small>{{ commentResource?.comment_count || 0 }}</small></h3>
        <div class="comment-list">
          <article v-for="item in comments" :key="item.id" class="comment-item">
            <div class="comment-author">
              <span class="avatar">{{ item.author_name.slice(0, 1).toUpperCase() }}</span>
              <strong>{{ item.author_name }}</strong>
              <time class="comment-meta">{{ new Date(item.created_at).toLocaleString() }}</time>
            </div>
            <p>{{ item.content }}</p>
            <button v-if="item.author_id === user?.id || user?.is_admin" @click="deleteComment(item)">删除</button>
          </article>
          <div v-if="!comments.length" class="comment-empty">还没有评论，来说说这份资料怎么样吧。</div>
        </div>
        <div class="comment-editor">
          <el-input v-model="commentContent" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="写下你的使用感受或补充建议" />
          <el-button type="primary" @click="submitComment">发表评论</el-button>
        </div>
      </aside>
    </div>
    <template #footer>
      <el-button v-if="commentResource && commentResource.owner_id !== user?.id" type="danger" plain @click="reportResource(commentResource)">举报资源</el-button>
      <el-button v-else disabled>不能举报自己的资源</el-button>
      <el-button @click="commentsOpen = false">关闭</el-button>
      <el-button type="primary" @click="commentResource && download(commentResource)">下载原文件</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="helpDialogOpen" title="发布资源求助" width="min(560px, 92vw)">
    <el-form label-position="top">
      <el-form-item label="需要什么资料"><el-input v-model="helpForm.title" placeholder="例如：2025 高等数学期末复习题" /></el-form-item>
      <el-form-item label="详细说明"><el-input v-model="helpForm.description" type="textarea" :rows="4" /></el-form-item>
      <div class="form-grid"><el-form-item label="学院"><el-input v-model="helpForm.college" /></el-form-item><el-form-item label="专业"><el-input v-model="helpForm.major" /></el-form-item></div>
      <el-form-item label="课程"><el-input v-model="helpForm.course" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="helpDialogOpen = false">取消</el-button><el-button type="primary" @click="createHelpRequest">发布求助</el-button></template>
  </el-dialog>

  <el-dialog v-model="guideOpen" title="欢迎来到拾页" width="min(760px, 92vw)" :close-on-click-modal="false" :show-close="false">
    <div class="guide-grid"><article><strong>1</strong><h3>寻找资料</h3><p>用关键词、学院、专业、课程和年份组合筛选，也可以直接询问 AI。</p></article><article><strong>2</strong><h3>分享资料</h3><p>填写使用经验和课程信息。大文件可以上传，超过 50 MB 会跳过 AI 解析。</p></article><article><strong>3</strong><h3>参与互助</h3><p>点赞、评论优质资料；找不到时发布资源求助，和其他同学一起“同求”。</p></article></div>
    <template #footer><el-button type="primary" size="large" @click="finishGuide">开始使用</el-button></template>
  </el-dialog>
</template>
