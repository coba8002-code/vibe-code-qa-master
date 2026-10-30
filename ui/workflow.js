/* GitHub read-only scan history and AI remediation proposal UI. */
document.addEventListener('DOMContentLoaded', () => {
  connectFromLauncher();
  const section = document.createElement('div');
  section.className = 'panel';
  const heading = document.createElement('h3');
  heading.textContent = '출시 준비 상태';
  const button = document.createElement('button');
  button.textContent = '출시 게이트 확인';
  button.onclick = showReleaseReadiness;
  const result = document.createElement('div');
  result.id = 'releaseReadiness';
  result.className = 'muted';
  result.textContent = 'Windows 실행·설치 및 실제 프로젝트 검증은 별도 확인이 필요합니다.';
  section.append(heading, button, result);
  document.querySelector('main').append(section);
  const repair = document.createElement('div');
  repair.className = 'panel';
  repair.innerHTML = '<h3>AI 자동 수정 · 재검사</h3><p>위에서 선택한 실행 검사 폴더의 복사본을 테스트하고, 실패하면 Codex 수정과 재검사를 최대 2회 진행합니다. 테스트 파일은 변경하지 않습니다. 소스가 로그인된 Codex에 전송되며 원본과 GitHub는 변경하지 않습니다.</p><button id="autoFixStart">선택한 폴더 자동 수정</button> <button id="autoFixRefresh">결과 새로고침</button><div id="autoFixJobs"></div>';
  document.querySelector('main').append(repair);
  $('autoFixStart').onclick = async () => {
    try {
      const project_id = $('runtimeProject').value;
      if (!project_id) throw Error('실행 검사 폴더를 먼저 선택하세요');
      await call('/api/autofix/jobs', 'POST', {project_id, rounds: 2});
      msg('복사본에서 자동 수정 시작'); await refreshAutoFix();
    } catch (e) { msg('자동 수정 시작 실패: ' + e.message); }
  };
  $('autoFixRefresh').onclick = refreshAutoFix;
  setInterval(() => { if ($('token').value) refreshAutoFix().catch(() => {}); }, 5000);
});

async function refreshAutoFix() {
  try {
    const jobs = await call('/api/autofix/jobs');
    $('autoFixJobs').innerHTML = jobs.map(j => '<div><b>' + esc(j.project) + ' · ' + esc(j.state) + '</b><p>' + esc(j.message || '') + '</p>' +
      '<details><summary>기준 테스트 및 재검사 결과</summary><pre style="white-space:pre-wrap">' + esc(JSON.stringify(j, null, 2)) + '</pre></details>' +
      (j.rounds.length ? '<button data-patch="' + esc(j.id) + '">수정 패치 다운로드</button>' : '') + '</div>').join('') || '자동 수정 이력 없음';
    $('autoFixJobs').querySelectorAll('[data-patch]').forEach(button => button.onclick = async () => {
      const response = await fetch('/api/autofix/jobs/' + button.dataset.patch + '/patch', {headers: {Authorization: 'Bearer ' + $('token').value}});
      if (!response.ok) { msg('패치 다운로드 실패'); return; }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = 'autofix.patch'; link.click(); URL.revokeObjectURL(url);
    });
  } catch (e) { msg('자동 수정 이력 확인 실패: ' + e.message); }
}

async function connectFromLauncher() {
  const code = new URLSearchParams(location.hash.slice(1)).get('connect');
  if (!code) return;
  history.replaceState(null, '', location.pathname + location.search);
  try {
    const response = await fetch('/api/session/browser', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code}), cache: 'no-store'
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || response.status);
    $('token').value = data.token;
    await refresh();
  } catch (error) { msg('자동 연결 실패: ' + error.message); }
}

async function showReleaseReadiness() {
  try {
    const data = await call('/api/release-readiness');
    const lines = data.blocking_gates.map(g => '<li>' + esc(g) + '</li>').join('');
    $('releaseReadiness').innerHTML = '<p>버전: ' + esc(data.version) + ' · 출시 가능: <b>아니요</b></p><ul>' + lines + '</ul>';
  } catch (error) { msg('출시 상태 확인 실패: ' + error.message); }
}

async function refreshGitHubWorkflow() {
  try {
    const [projects, scans, drafts, proposals, rechecks, followups] = await Promise.all([
      call('/api/projects'), call('/api/scans'), call('/api/repair-drafts'), call('/api/patch-proposals'), call('/api/rechecks'), call('/api/followup-drafts')
    ]);
    $('approvedRepos').innerHTML = projects.filter(p => p.state === 'approved').map(p =>
      `<p>${esc(p.owner)}/${esc(p.repo)} <button onclick="syncApprovedRepo(${p.id})">커밋 고정 검수</button></p>`
    ).join('') || '승인된 저장소 없음';
    $('savedScans').innerHTML = scans.map(s =>
      `<p>검수 #${s.id} · ${esc(s.revision.slice(0, 12))} · ${esc(s.created_at)}` +
      ` <button onclick="viewSavedScan(${s.id})">결과 보기</button>` +
      ` <button onclick="recheckLocalProject(${s.id})">수정 후 재검수</button>` +
      ` <button onclick="draftFix(${s.id},'codex')">Codex 요청서</button>` +
      ` <button onclick="draftFix(${s.id},'claude-code')">Claude 요청서</button></p>`
    ).join('') || '검수 이력 없음';
    const results = $('recheckResults');
    if (results) results.innerHTML = rechecks.map(r => {
      const c = r.comparison;
      return `<p>재검수 #${r.id} · 기준 검수 #${r.scan_id} · 해결 후보 ${c.resolved_candidates.length}개 · 잔여 ${c.remaining.length}개 · 새 발견 ${c.new_findings.length}개 · 건너뜀 ${c.files_skipped}개 <button onclick="showRecheckDetail(${r.id})">상세</button>` +
        ` <button onclick="createFollowup(${r.id},'codex')">Codex 후속 요청</button>` +
        ` <button onclick="createFollowup(${r.id},'claude-code')">Claude 후속 요청</button></p>`;
    }).join('') || '아직 재검수 기록 없음';
    let followupPanel = $('followupDrafts');
    if (!followupPanel && $('recheckResults')) {
      const section = document.createElement('div');
      section.className = 'panel';
      const title = document.createElement('h3'); title.textContent = 'AI 후속 수정 요청서';
      followupPanel = document.createElement('div'); followupPanel.id = 'followupDrafts';
      section.append(title, followupPanel);
      $('recheckResults').closest('.panel').after(section);
    }
    if (followupPanel) followupPanel.innerHTML = followups.map(f =>
      `<p>후속 요청서 #${f.id} · ${esc(f.provider)} · ${f.round}/5차` +
      ` <button onclick="downloadFollowup(${f.id})">MD 다운로드</button></p>`
    ).join('') || '후속 요청서 없음';
    $('repairDrafts').innerHTML = drafts.map(d =>
      `<p>요청서 #${d.id} · ${esc(d.provider)} · ${esc(d.status)}` +
      ` <button onclick="downloadRepairDraft(${d.id})">MD 다운로드</button>` +
      ` <button onclick="submitPatchFromFile(${d.id})">패치 등록</button></p>`
    ).join('') || '요청서 없음';
    const panel = $('patchProposals');
    if (panel) panel.innerHTML = proposals.map(p =>
      `<p>패치 #${p.id} · ${esc(p.status)} · ${esc(p.summary)}` +
      ` <button onclick="viewPatch(${p.id})">검토/내보내기</button></p>`
    ).join('') || '등록된 패치 없음';
  } catch (error) { msg('GitHub 워크플로 확인 실패: ' + error.message); }
}

async function createFollowup(recheckId, provider) {
  try {
    const result = await call('/api/rechecks/' + recheckId + '/followup', 'POST', {provider});
    msg(provider + ' 후속 수정 요청서 #' + result.id + ' 생성 완료. AI 실행이나 GitHub 변경은 하지 않았습니다.');
    await refreshGitHubWorkflow();
  } catch (error) { msg('후속 요청서 생성 실패: ' + error.message); }
}

async function downloadFollowup(id) {
  try {
    const draft = await call('/api/followup-drafts/' + id);
    const blob = new Blob([draft.instructions], {type:'text/markdown;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url;
    link.download = 'qa-followup-' + id + '.md'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { msg('다운로드 실패: ' + error.message); }
}

async function recheckLocalProject(scanId) {
  const files = Array.from($('recheckFolder').files);
  if (!files.length) return msg('먼저 재검수할 로컬 프로젝트 폴더를 선택하세요.');
  if (!confirm('선택한 로컬 폴더를 기준 검수 #' + scanId + '와 정적 비교할까요? GitHub나 소스는 변경하지 않습니다.')) return;
  const form = new FormData();
  for (const file of files) {
    form.append('files', file, file.name);
    form.append('paths', file.webkitRelativePath || file.name);
  }
  try {
    msg('수정 후 재검수 중...');
    const response = await fetch('/api/scans/' + scanId + '/recheck', {
      method: 'POST', headers: {Authorization: 'Bearer ' + $('token').value}, body: form
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.detail || response.status);
    msg('재검수 저장 완료. 비교 결과는 정적 패턴 기준이며 기능 정상화 판정이 아닙니다.');
    await refreshGitHubWorkflow();
  } catch (error) { msg('재검수 실패: ' + error.message); }
}

async function showRecheckDetail(id) {
  try {
    const rows = await call('/api/rechecks');
    const row = rows.find(r => r.id === id);
    if (!row) return;
    const c = row.comparison;
    $('recheckResults').innerHTML = `<button onclick="refreshGitHubWorkflow()">목록으로 돌아가기</button>` +
      [['해결 후보', c.resolved_candidates], ['남은 문제', c.remaining], ['새 발견', c.new_findings]]
      .map(([name, rows]) => `<h4>${esc(name)} · ${rows.length}건</h4>` +
        (rows.map(x => `<p>${esc(x.rule)} — ${esc(x.path)}</p>`).join('') || '<p>없음</p>')).join('') +
      `<p>${esc(c.note)}</p>`;
  } catch (error) { msg(error.message); }
}

async function submitPatchFromFile(draftId) {
  const picker = document.createElement('input');
  picker.type = 'file'; picker.accept = '.diff,.patch,text/plain';
  picker.onchange = async () => {
    const file = picker.files[0];
    if (!file || file.size > 300000) return msg('300KB 이하 diff 파일만 등록할 수 있습니다.');
    const summary = prompt('패치의 수정 내용과 테스트 결과를 간단히 적어주세요.');
    if (!summary) return;
    try {
      const response = await call('/api/patch-proposals', 'POST', {
        draft_id: draftId, patch: await file.text(), summary
      });
      msg('패치 #' + response.id + ' 등록됨. 아직 적용하지 않았습니다.');
      await refreshGitHubWorkflow();
    } catch (error) { msg('패치 등록 실패: ' + error.message); }
  };
  picker.click();
}

async function viewPatch(id) {
  try {
    const result = await call('/api/patch-proposals/' + id);
    if (!confirm('패치 #' + id + '의 전체 diff 파일을 내려받아 검토하시겠습니까?\n' + result.summary)) return;
    const blob = new Blob([result.patch], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url;
    link.download = 'review-patch-' + id + '.diff'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    if (result.status === 'pending_review') {
      const choice = confirm('전체 diff 파일과 테스트 결과를 충분히 확인하셨습니까?\n확인 = 다운로드 승인 / 취소 = 반려 또는 검토 보류');
      const decision = choice ? 'approved_for_export' : 'rejected';
      if (!choice && !confirm('패치를 반려하시겠습니까? 취소하면 검토 대기 상태로 둡니다.')) return;
      await call('/api/patch-proposals/' + id + '/review', 'POST', {decision});
      await refreshGitHubWorkflow();
      if (!choice) return;
    }
    msg('패치를 파일로 내보냈습니다. 적용과 GitHub 반영은 별도 작업입니다.');
  } catch (error) { msg('패치 검토 실패: ' + error.message); }
}

async function syncApprovedRepo(id) {
  try {
    if (!confirm('GitHub의 최신 커밋을 읽고 검수 이력을 저장할까요? 쓰기 작업은 하지 않습니다.')) return;
    msg('커밋 고정 검수 중...');
    const result = await call('/api/projects/' + id + '/sync', 'POST');
    showScan(result.report);
    msg('커밋 ' + result.revision.slice(0, 12) + ' 검수 저장 완료');
    await refreshGitHubWorkflow();
  } catch (error) { msg('검수 실패: ' + error.message); }
}

async function viewSavedScan(id) {
  try {
    const result = await call('/api/scans/' + id);
    showScan(result.result);
    window.scrollTo({top: 0, behavior: 'smooth'});
  } catch (error) { msg(error.message); }
}

async function draftFix(id, provider) {
  try {
    const result = await call('/api/repair-drafts', 'POST', {scan_id: id, provider});
    msg('수정 요청서 #' + result.id + ' 생성 완료. GitHub 변경 없음.');
    await refreshGitHubWorkflow();
  } catch (error) { msg('요청서 생성 실패: ' + error.message); }
}

async function downloadRepairDraft(id) {
  try {
    const draft = await call('/api/repair-drafts/' + id);
    const blob = new Blob([draft.instructions], {type: 'text/markdown;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'repair-draft-' + id + '.md';
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) { msg('다운로드 실패: ' + error.message); }
}
