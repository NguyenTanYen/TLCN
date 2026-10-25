// Trợ giúp cho người mới: khung "Trang này dùng để làm gì?" (có thể thu gọn) và trang Hướng dẫn sử dụng có giải thích từ ngữ.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { auth } from '../api'
import { Card } from './ui'

/** Khung giải thích ngắn ở đầu trang. Nhớ trạng thái đóng/mở trong trình duyệt (nếu có thể). */
export function PageHelp({ id, title = 'Hướng dẫn cho trang này', children }) {
  const key = `help-${id}`
  const [open, setOpen] = useState(() => { try { return localStorage.getItem(key) === 'open' } catch { return true } })
  const toggle = () => { const v = !open; setOpen(v); try { localStorage.setItem(key, v ? 'open' : 'closed') } catch { /* bỏ qua */ } }
  return <div className={`pagehelp ${open ? 'open' : ''}`}>
    <button type="button" className="pagehelp-h" aria-expanded={open} onClick={toggle}><span aria-hidden="true">ⓘ</span> {title} <span className="pagehelp-t">{open ? 'Thu gọn' : 'Xem'}</span></button>
    {open && <div className="pagehelp-b">{children}</div>}
  </div>
}

export const GLOSSARY = [
  ['Môn học / Học phần', 'Một môn trong chương trình đào tạo, ví dụ "Hệ quản trị cơ sở dữ liệu". Mỗi môn có đề cương chi tiết.'],
  ['Lớp học phần', 'Một lớp cụ thể của môn trong một học kỳ, do một giảng viên phụ trách, ví dụ DBMS330284_01. Sinh viên ghi danh vào lớp học phần.'],
  ['Chuẩn đầu ra môn học (CLO)', 'Những điều sinh viên phải làm được sau khi học xong môn, ví dụ "Viết được thủ tục và trigger bằng T-SQL". Mỗi môn có vài CLO (CLO1, CLO2…).'],
  ['Chuẩn đầu ra chương trình (PLO) và chỉ báo (PI)', 'PLO là điều sinh viên cần đạt khi tốt nghiệp ngành. PI là các tiêu chí nhỏ hơn dùng để đo từng PLO. Mỗi CLO của môn góp phần đo một hoặc vài PI.'],
  ['Đề cương chi tiết', 'Tài liệu mô tả môn: mục tiêu, chuẩn đầu ra, nội dung từng chương, cách đánh giá, tài liệu học tập. Bộ môn soạn và duyệt, giảng viên chỉ xem bản đang áp dụng.'],
  ['Ngân hàng câu hỏi', 'Kho câu hỏi của môn. Mỗi câu gắn với một chương, một mức độ nhận thức và một hoặc vài CLO để hệ thống biết câu đó đo điều gì.'],
  ['Mức độ nhận thức (Bloom)', 'Độ khó theo kiểu tư duy: Nhớ, Hiểu, Vận dụng, Phân tích, Đánh giá, Sáng tạo.'],
  ['Ma trận đề', 'Bảng chọn số câu theo từng chương và từng mức độ nhận thức, để đề thi cân đối và phủ đủ các CLO. Hệ thống dựa vào đó để tự chọn câu hỏi.'],
  ['Bài kiểm tra trực tuyến (Quiz Moodle)', 'Bài trắc nghiệm sinh viên làm trên Moodle. Hệ thống tạo sẵn bài này trên Moodle và lấy kết quả về.'],
  ['Phiếu trả lời và chấm phiếu', 'Với bài thi giấy, sinh viên tô vào phiếu trả lời. Giảng viên quét hoặc chụp ảnh phiếu, hệ thống đọc ô đã tô và chấm điểm.'],
  ['Lấy bài làm (đồng bộ)', 'Kéo bài làm của sinh viên từ Moodle về hệ thống. Cần làm trước khi phân tích.'],
  ['Phân tích bài kiểm tra', 'Hệ thống tính điểm, độ khó và độ phân biệt của từng câu, tỷ lệ sinh viên đạt từng CLO của lớp và các chương sinh viên còn yếu.'],
  ['Độ khó (p) và độ phân biệt (DI)', 'p là tỷ lệ sinh viên làm đúng câu (càng thấp càng khó). DI cho biết câu đó có phân biệt được sinh viên giỏi và yếu hay không; DI thấp nghĩa là câu hỏi nên xem lại.'],
  ['Ngưỡng đạt và chỉ tiêu', 'Ngưỡng đạt: điểm tối thiểu (tính theo % điểm của các câu thuộc CLO) để một sinh viên được tính là đạt CLO đó. Chỉ tiêu: tỷ lệ sinh viên của lớp cần đạt để kết luận lớp đạt CLO.'],
  ['Minh chứng', 'Bài kiểm tra được dùng làm căn cứ để kết luận kết quả CLO của lớp. Giảng viên chọn bài nào được tính.'],
  ['Biểu mẫu BM6 (6a, 6b, 6c)', 'Biểu mẫu của nhà trường báo cáo kết quả đo chuẩn đầu ra môn học: 6a là kế hoạch kiểm tra, 6b là kết quả tổng hợp của lớp, 6c là bảng minh chứng điểm.'],
  ['Biểu mẫu BM2, BM3 (b, c)', 'Biểu mẫu của bộ môn/chương trình: BM3b là kế hoạch đo PI, BM3c là kết quả từng PLO, BM2 là tổng kết chương trình.'],
  ['Ôn tập', 'Sau khi có kết quả, hệ thống chỉ ra sinh viên còn yếu ở chương nào, rồi tạo bài kiểm tra lại gồm các câu đã sai và câu tương tự cho từng sinh viên hoặc cả nhóm.'],
]

const STEPS = {
  lecturer: [
    ['Chọn môn và lớp', 'Vào "Môn học của tôi", bấm tên môn để xem đề cương, hoặc bấm "Mở lớp" để làm việc với một lớp học phần.'],
    ['Soạn câu hỏi', 'Vào "Ngân hàng câu hỏi" để thêm câu hỏi, hoặc nhập nhiều câu từ file. Mỗi câu cần chọn chương, mức độ nhận thức và CLO.'],
    ['Tạo bài kiểm tra', 'Bấm "Tạo bài kiểm tra" ở trang môn hoặc trang lớp. Chọn hình thức (trực tuyến, trên giấy, nhập điểm), để hệ thống chọn câu theo ma trận đề hoặc tự chọn câu, rồi lưu.'],
    ['Đưa bài cho sinh viên', 'Bài trực tuyến: bấm "Tạo bài trắc nghiệm trên Moodle". Bài giấy: sinh mã đề, in đề và phiếu trả lời. Nếu tạo ở trang môn, bạn chọn giao cho lớp nào ở bước này.'],
    ['Lấy kết quả và phân tích', 'Sau khi sinh viên làm xong, bấm "Lấy bài làm từ Moodle" (hoặc chấm phiếu) rồi "Phân tích". Xem điểm, câu hỏi, thời gian làm bài và cảnh báo bất thường.'],
    ['Xem kết quả chuẩn đầu ra của lớp', 'Vào "Kết quả chuẩn đầu ra của lớp" để xem tỷ lệ sinh viên đạt từng CLO và xuất biểu mẫu BM6.'],
    ['Ôn tập cho sinh viên còn yếu', 'Vào "Ôn tập" để xem sinh viên yếu ở chương nào và tạo bài kiểm tra lại cho một sinh viên hoặc cả nhóm.'],
  ],
  admin: [
    ['Khai báo chương trình đào tạo', 'Vào "Chương trình đào tạo": xem chuẩn đầu ra chương trình (PLO), chỉ báo (PI) và danh sách học phần theo học kỳ.'],
    ['Khai báo học phần', 'Vào "Học phần": thêm môn, các chương, chuẩn đầu ra môn học (CLO) và gắn mỗi CLO với PI.'],
    ['Soạn đề cương chi tiết', 'Trong trang học phần, soạn đề cương (nháp), kiểm tra tỷ trọng đánh giá đủ 100%, rồi duyệt. Muốn sửa bản đã duyệt thì tạo phiên bản mới.'],
    ['Mở lớp học phần', 'Gán giảng viên phụ trách và học kỳ cho từng lớp. Giảng viên chỉ thấy các lớp được gán.'],
    ['Lập kế hoạch đo PI', 'Vào "Kế hoạch đo chỉ báo (PI)": chọn môn nào, học kỳ nào, giảng viên nào chịu trách nhiệm đo từng PI.'],
    ['Xem kết quả chương trình', 'Vào "Kết quả chương trình (PLO)" để tính lại kết quả, xem tỷ lệ đạt từng PLO và xuất biểu mẫu BM2, BM3.'],
    ['Kiểm tra kết nối Moodle', 'Vào "Kết nối Moodle" để xem hệ thống đã nối với Moodle chưa.'],
  ],
}

export default function Guide() {
  const role = auth.user()?.role === 'admin' ? 'admin' : 'lecturer'
  return <>
    <div className="page-h"><div><h1>Hướng dẫn sử dụng</h1>
      <p className="muted">Dành cho người mới: các bước làm việc chính và giải thích những từ chuyên môn xuất hiện trong hệ thống.</p></div></div>
    <Card title={role === 'admin' ? 'Các bước làm việc của Bộ môn' : 'Các bước làm việc của giảng viên'}>
      <ol className="guide-steps">{STEPS[role].map(([t, d], i) => <li key={t}><span className="n">{i + 1}</span><div><b>{t}</b><p>{d}</p></div></li>)}</ol></Card>
    <Card title="Giải thích từ ngữ">
      <table className="tbl"><thead><tr><th style={{ width: '28%' }}>Từ ngữ</th><th>Ý nghĩa</th></tr></thead>
        <tbody>{GLOSSARY.map(([k, v]) => <tr key={k}><td><b>{k}</b></td><td>{v}</td></tr>)}</tbody></table></Card>
    <Card title="Lưu ý quan trọng">
      <ul className="guide-notes">
        <li>Hệ thống đánh giá chuẩn đầu ra (CLO) cho <b>cả lớp</b>, không chấm CLO riêng cho từng sinh viên. Với từng sinh viên, bạn xem điểm, chương còn yếu và các câu làm sai.</li>
        <li>Sinh viên xem điểm và gợi ý ôn tập trên Moodle, sau khi giảng viên bấm "Công bố kết quả".</li>
        <li>Khi cần giúp đỡ, mở lại trang này hoặc bấm biểu tượng ⓘ ở đầu mỗi trang.</li>
      </ul><p className="muted small">Quay về <Link to="/">trang chính</Link>.</p></Card>
  </>
}
