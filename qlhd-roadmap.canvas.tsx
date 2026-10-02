import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Text,
  useHostTheme,
} from "cursor/canvas";

const phases = [
  {
    id: "P0",
    title: "P0 · Chốt nền tảng và baseline",
    status: "Baseline đã kiểm chứng",
    outcome: "Một bản chạy local ổn định, biết rõ source, database và dữ liệu mẫu.",
    work: [
      "Đọc và đối chiếu models, forms, views, urls, signals, financial, apps.",
      "Đã thống nhất MySQL cho vận hành và SQLite riêng cho kiểm thử.",
      "Chạy manage.py check, test hiện có, kiểm tra migration và git diff.",
      "Tạo bộ dữ liệu kiểm thử tối thiểu cho PHCN, CSXH, kỳ 1 và kỳ 2.",
    ],
    gate: "Không sửa nghiệp vụ lớn trước khi baseline chạy được.",
  },
  {
    id: "P1",
    title: "P1 · Hoàn thiện hợp đồng chính thức",
    status: "Đã có luồng và hồi quy",
    outcome: "Proposal được duyệt có thể tạo một HopDong hợp lệ, an toàn và truy vết được.",
    work: [
      "Chuẩn hóa POST duyệt đề xuất và trạng thái DA_DUYET.",
      "Tạo hợp đồng trong transaction từ PhanBoChiTieu, không tin giá trị từ client.",
      "Tạo ChiTietKhoiLuongHopDong và snapshot financial cần thiết.",
      "Cập nhật DA_TAO_HOP_DONG, khóa dữ liệu đúng thời điểm, xử lý lỗi rõ ràng.",
    ],
    gate: "Giá trị hợp đồng không đổi khi assignment thay đổi.",
  },
  {
    id: "P2",
    title: "P2 · Word hợp đồng + Phụ lục 2 kỳ 1",
    status: "Đã có mẫu xuất",
    outcome: "Xuất được một file Word hoàn chỉnh gồm hợp đồng chính và Phụ lục 2 kỳ 1.",
    work: [
      "Tìm và tái sử dụng cơ chế docx/python-docx/docxtpl hiện có nếu có.",
      "Xây context tài chính từ allocation và context danh sách từ PhanCongTre.",
      "Snapshot kỳ 1 để tài liệu đã phát hành không bị thay đổi về sau.",
      "Kiểm tra placeholder, định dạng tiền Việt Nam, ngày tháng và trang in.",
    ],
    gate: "File mở được, đủ nội dung và không phụ thuộc dữ liệu phân công tương lai.",
  },
  {
    id: "P3",
    title: "P3 · Export Phụ lục kỳ 2+",
    status: "Đã có luồng xuất",
    outcome: "Mỗi kỳ từ kỳ 2 trở đi xuất được file riêng mà không tạo HĐ/phụ lục DB mới.",
    work: [
      "Lọc PhanCongTre theo hợp đồng và ky_phan_cong.",
      "Chuẩn hóa quy tắc ngày phân công khi một kỳ có nhiều ngày.",
      "Dùng cùng bộ template/context với kỳ 1 ở mức phù hợp.",
      "Bổ sung liên kết tải file và kiểm soát kỳ không hợp lệ.",
    ],
    gate: "Kỳ 2+ không làm thay đổi gia_tri_hop_dong.",
  },
  {
    id: "P4",
    title: "P4 · Ghi nhận thực hiện và thanh toán",
    status: "Đã có sổ phiếu và bảo vệ dữ liệu",
    outcome: "Theo dõi được thực tế đã làm và thanh toán đúng khối lượng hợp lệ, không trùng.",
    work: [
      "Thiết kế NhatKyThucHien theo dòng phân công, dịch vụ, ngày và số buổi.",
      "Chặn ghi nhận vượt phạm vi hợp đồng/phân công nếu nghiệp vụ yêu cầu.",
      "Xây DotThanhToan và ChiTietThanhToan với quy tắc chống thanh toán trùng.",
      "Tách rõ khối lượng hợp đồng, thực hiện và thanh toán.",
    ],
    gate: "Có thể đối chiếu từng khoản thanh toán về nguồn thực hiện.",
  },
  {
    id: "P5",
    title: "P5 · Nghiệm thu, thanh lý, báo cáo và UAT",
    status: "Cần UAT vận hành",
    outcome: "Có quy trình đóng hợp đồng, báo cáo và bộ kiểm thử để chạy thật.",
    work: [
      "Kiểm soát chuyển trạng thái nghiệm thu/thanh lý theo điều kiện.",
      "Báo cáo theo cán bộ, địa bàn, dịch vụ, kỳ, ngân sách và thanh toán.",
      "Phân quyền, nhật ký thao tác, backup/restore và hướng dẫn vận hành.",
      "UAT với dữ liệu thực tế đã ẩn danh, sửa lỗi và chốt bản phát hành.",
    ],
    gate: "Người dùng nghiệp vụ hoàn thành UAT và có quy trình vận hành thật.",
  },
];

function PhaseCard({ phase }: { phase: (typeof phases)[number] }) {
  const theme = useHostTheme();
  return (
    <Card style={{ height: "100%" }}>
      <CardHeader trailing={<Pill size="sm">{phase.status}</Pill>}>
        {phase.id}
      </CardHeader>
      <CardBody>
        <Stack gap={8}>
          <H3>{phase.title}</H3>
          <Text tone="secondary">{phase.outcome}</Text>
          <Divider />
          <Text weight="semibold">Phạm vi chính</Text>
          <Stack gap={5}>
            {phase.work.map((item) => (
              <Text key={item} size="small" tone="secondary">
                · {item}
              </Text>
            ))}
          </Stack>
          <Text size="small" style={{ color: theme.accent.primary }}>
            Cổng nghiệm thu: {phase.gate}
          </Text>
        </Stack>
      </CardBody>
    </Card>
  );
}

export default function QLHDRoadmap() {
  const theme = useHostTheme();
  return (
    <Stack
      gap={20}
      style={{
        padding: 24,
        maxWidth: 1180,
        margin: "0 auto",
        color: theme.text.primary,
      }}
    >
      <Stack gap={8}>
        <Row gap={8} align="center">
          <Pill active>QLHD</Pill>
          <Text size="small" tone="secondary">Cập nhật 02/10/2026 · main · nền 5628f468</Text>
        </Row>
        <H1>Lộ trình từ baseline đến vận hành</H1>
        <Text tone="secondary">
          Các luồng chính đã có. SQLite: 180 test đạt, 3 test đồng thời cần MySQL bị bỏ qua. Ba ca HTTP đạt; giao diện Edge còn cần kiểm tra trên Windows.
        </Text>
      </Stack>

      <Callout tone="warning" title="Phần còn cần nghiệm thu">
        MySQL là CSDL vận hành; SQLite dùng kiểm thử. ĐNTT Word đã bỏ trang trắng trên fixture. Cần đối soát bản sao dữ liệu thật, mở Word/Excel desktop và chạy ba ca UAT bằng Edge. Báo cáo địa bàn/PDF nhà tài trợ cần chốt chỉ tiêu và mẫu trước khi bổ sung.
      </Callout>

      <Grid columns={3} gap={12}>
        <Card>
          <CardHeader>Đích cuối</CardHeader>
          <CardBody><Text weight="semibold">Chạy được với quy trình đầy đủ</Text><Text size="small" tone="secondary">Từ phân bổ đến báo cáo và thanh lý.</Text></CardBody>
        </Card>
        <Card>
          <CardHeader>Nguyên tắc dữ liệu</CardHeader>
          <CardBody><Text weight="semibold">Database là nguồn sự thật</Text><Text size="small" tone="secondary">Word, PDF và Excel chỉ là đầu ra.</Text></CardBody>
        </Card>
        <Card>
          <CardHeader>Cách làm việc</CardHeader>
          <CardBody><Text weight="semibold">Mỗi mốc đều có test</Text><Text size="small" tone="secondary">Không chuyển phase khi chưa qua cổng nghiệm thu.</Text></CardBody>
        </Card>
      </Grid>

      <H2>Các giai đoạn và phạm vi kiểm chứng</H2>
      <Grid columns={2} gap={16}>
        {phases.map((phase) => <PhaseCard key={phase.id} phase={phase} />)}
      </Grid>

      <Stack gap={8}>
        <H2>Bằng chứng và bước vận hành</H2>
        <Text>1. docs/PROJECT_PROGRESS.md ghi kết quả từng đợt; kết quả MySQL cũ không thay lần chạy mới.</Text>
        <Text>2. docs/UAT_CURRENT.md hướng dẫn ba ca tạo/sửa/xóa, lập/hủy/chi phiếu và kiểm tra dữ liệu đã thanh toán.</Text>
        <Text>3. Edge 154.0.4258.53 không khởi động trong phiên kiểm thử do hạn chế socket; chưa xác minh JavaScript/bố cục trên Edge.</Text>
        <Text tone="secondary" size="small">Các dòng phạm vi trong từng thẻ là cổng nghiệm thu, không khẳng định mọi dữ liệu vận hành đã được kiểm tra.</Text>
      </Stack>
    </Stack>
  );
}
