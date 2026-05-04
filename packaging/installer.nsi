; ============================================================
;  BudgetTracker Windows 安装包 — NSIS 脚本
;  用法: makensis /DVERSION=1.0.0 packaging\installer.nsi
;  输出: dist\BudgetTracker-${VERSION}-setup.exe
; ============================================================

!ifndef VERSION
  !define VERSION "1.0.0"
!endif

; ─── 基础配置 ─────────────────────────────────────────────
Name "BudgetTracker"
OutFile "dist\BudgetTracker-${VERSION}-setup.exe"
InstallDir "$PROGRAMFILES\BudgetTracker"
InstallDirRegKey HKLM "Software\BudgetTracker" "InstallDir"
RequestExecutionLevel admin

SetCompressor /SOLID lzma
SetCompressorDictSize 64

; ─── 界面 ─────────────────────────────────────────────────
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "dist\installer\budgettracker.ico"
!define MUI_UNICON "dist\installer\budgettracker.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ─── 安装 ─────────────────────────────────────────────────
Section "Install"
  SetOutPath "$INSTDIR"

  File "dist\installer\BudgetTracker.exe"

  ; 开始菜单快捷方式
  CreateDirectory "$SMPROGRAMS\BudgetTracker"
  CreateShortcut "$SMPROGRAMS\BudgetTracker\BudgetTracker.lnk" "$INSTDIR\BudgetTracker.exe"
  CreateShortcut "$SMPROGRAMS\BudgetTracker\Uninstall.lnk" "$INSTDIR\uninstall.exe"

  ; 桌面快捷方式
  CreateShortcut "$DESKTOP\BudgetTracker.lnk" "$INSTDIR\BudgetTracker.exe"

  ; 写入卸载信息
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "DisplayName" "BudgetTracker - 固定资产与生活支出统计"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "DisplayIcon" "$INSTDIR\BudgetTracker.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "Publisher" "BudgetApp"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker" \
    "NoRepair" 1

  WriteRegStr HKLM "Software\BudgetTracker" "InstallDir" "$INSTDIR"
SectionEnd

; ─── 卸载 ─────────────────────────────────────────────────
Section "Uninstall"
  Delete "$INSTDIR\BudgetTracker.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\BudgetTracker\BudgetTracker.lnk"
  Delete "$SMPROGRAMS\BudgetTracker\Uninstall.lnk"
  RMDir "$SMPROGRAMS\BudgetTracker"

  Delete "$DESKTOP\BudgetTracker.lnk"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker"
  DeleteRegKey HKLM "Software\BudgetTracker"
SectionEnd
