export class ApiConfig {
  // ===== 网络地址配置 =====
  // 真机调试 (hdc rport): 使用 127.0.0.1
  // 模拟器调试: 使用 10.0.2.2 (模拟器访问宿主机的特殊地址)
  // 局域网调试: 使用宿主机实际 IP (如 10.229.132.64)
  static readonly BASE_URL: string = 'http://10.0.2.2:9000';
  static readonly baseUrl: string = 'http://10.0.2.2:9000';
  static readonly dashboardEndpoint: string = '/analytics/dashboard';
  static readonly uploadEndpoint: string = '/upload';
  static readonly analyzeEndpoint: string = '/analyze/json';
  static readonly reportsEndpoint: string = '/reports';
}
