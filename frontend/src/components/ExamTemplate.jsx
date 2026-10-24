// Trang đề của môn (chưa gắn lớp HP): xem nội dung, giao cho lớp HP khi xuất, tải Moodle XML, xóa.
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, STATUS_VI } from '../api'
import { ActionButton, Badge, Card, Crumbs, Stat } from './ui'
import { DeployDialog, TYPE_VI } from './NewExam'

const NEXT = {
  online: 'Mỗi lớp được tạo Quiz trên khóa học Moodle đã gắn; SV làm bài trên Moodle, rồi đồng bộ và phân tích ở bài của lớp.',
  paper: 'Mỗi lớp có bài riêng để sinh mã đề, in đề – phiếu trả lời và chấm phiếu theo danh sách SV của lớp.',
  manual: 'Mỗi lớp có bảng điểm riêng theo danh sách SV để nhập tay hoặc nhập từ Excel.',
}

export default function ExamTemplate({ e, reload }) {
  const nav = useNavigate()
  const [dep, setDep] = useState(false)
  const total = e.questions.reduce((a, q) => a + q.points, 0)
  return <>
    <div className="page-h">
      <div><Crumbs items={[['/', 'Môn học của tôi'], [`/courses/${e.course_id}`, e.course_code], [`/courses/${e.course_id}?tab=exams`, 'Đề kiểm tra'], [null, `Đề #${e.id}`]]} />
        <h1>{e.exam_title} <Badge tone="blue">Đề của môn</Badge></h1>
        <p className="muted">{e.course_code} – {e.course_name} · {TYPE_VI[e.exam_type]} · loại đánh giá {e.assessment_type === 'final' ? 'Cuối kỳ' : 'Quá trình'} ·
          {' '}{e.questions.length} {e.exam_type === 'manual' ? 'câu/ý' : 'câu'} · thang điểm {e.max_score}{e.duration_minutes ? ` · ${e.duration_minutes} phút` : ''}</p></div>
      <div className="row gap wrap">
        {e.exam_type === 'online' && <ActionButton className="btn" onRun={() => api.download(`/api/exams/${e.id}/moodle-xml`, `de_${e.id}_moodle.xml`)}>⬇ Moodle XML</ActionButton>}
        <ActionButton className="btn danger" confirm={`Xóa đề "${e.exam_title}"? Các bài đã giao cho lớp vẫn được giữ.`}
          onRun={async () => { await api.del(`/api/exams/${e.id}`); nav(`/courses/${e.course_id}?tab=exams`) }}>Xóa đề</ActionButton>
        <button className="btn primary" onClick={() => setDep(true)}>Giao cho lớp HP / Xuất</button>
      </div>
    </div>
    <div className="alert blue row gap wrap">
      <span><b>Đề chưa gắn lớp học phần.</b> Bấm <b>Giao cho lớp HP / Xuất</b> để chọn các lớp sẽ làm bài. {NEXT[e.exam_type]}</span>
    </div>
    <div className="grid2">
      <Card title={`Nội dung đề (${e.questions.length} ${e.exam_type === 'manual' ? 'câu/ý' : 'câu'} · tổng ${total} điểm thô)`}>
        <div className="scroll"><table className="tbl compact"><thead><tr><th>#</th><th>{e.exam_type === 'manual' ? 'Câu / ý chấm điểm' : 'Câu hỏi'}</th><th>CLO</th><th className="num-c">Điểm</th></tr></thead>
          <tbody>{e.questions.map(q => <tr key={q.question_id} className={q.is_cancelled ? 'cancel' : ''}><td>{q.order_index}</td>
            <td className="wrap-cell">{q.content}</td><td>{q.clos}</td><td className="num-c">{q.points}</td></tr>)}</tbody></table></div>
      </Card>
      <div className="stack">
        <div className="stats two">
          <Stat label="Đã giao cho" value={`${e.deployments.length} lớp`} sub={e.deployments.length ? e.deployments.map(d => d.section_code).join(', ') : 'chưa giao lớp nào'} />
          <Stat label="Bài làm đã có" value={e.deployments.reduce((a, d) => a + d.n_attempts, 0)} sub="cộng các lớp" />
        </div>
        <Card title="Các lớp đã giao" actions={<button className="btn sm primary" onClick={() => setDep(true)}>+ Giao thêm lớp</button>}>
          {e.deployments.length ? <table className="tbl compact"><thead><tr><th>Lớp</th><th>Học kỳ</th><th>Trạng thái</th><th>Moodle</th><th className="num-c">Bài làm</th><th /></tr></thead>
            <tbody>{e.deployments.map(d => <tr key={d.exam_id}><td><b>{d.section_code}</b></td><td>{d.semester}</td>
              <td><Badge tone={d.status === 'Analyzed' ? 'green' : d.status === 'Draft' ? 'gray' : 'blue'}>{STATUS_VI[d.status]}</Badge></td>
              <td>{d.moodle_quiz_id ? `Quiz #${d.moodle_quiz_id}` : '—'}</td><td className="num-c">{d.n_attempts}</td>
              <td><Link className="btn sm" to={`/exams/${d.exam_id}`}>Mở bài của lớp</Link></td></tr>)}</tbody></table>
            : <p className="muted">Chưa giao cho lớp nào.</p>}
        </Card>
      </div>
    </div>
    {dep && <DeployDialog e={e} onClose={() => setDep(false)} onDone={reload} />}
  </>
}
