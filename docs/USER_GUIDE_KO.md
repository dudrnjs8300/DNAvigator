# DNAvigator 사용자 매뉴얼 (한국어)

버전: 0.6.0 기준. 이 문서는 실제 구현된 화면과 메뉴만 설명한다 — 존재하지 않는 버튼은 적지 않는다.

## 1. 설치

### Installer (권장)

GitHub Releases(`https://github.com/dudrnjs8300/DNAvigator/releases/latest`)에서
`DNAvigator-X.Y.Z-win-x64-setup.exe`를 내려받아 실행한다. 관리자 권한이 필요 없다.
자세한 단계는 저장소 루트의 `README.md` 참고.

### Portable

압축 해제만 해서 쓰고 싶다면 같은 Release 페이지의 `DNAvigator-portable-win-x64.zip`을 원하는
위치에 압축 해제한다(한글이나 공백이 포함된 경로도 문제없다). 압축 해제된 폴더 안의
`DNAvigator.exe`를 실행하면 된다. 별도의 Python 설치도 필요 없다.

### 첫 실행 시 확인 사항

Windows Defender/SmartScreen이 서명되지 않은 실행파일이라는 경고를 표시할 수 있다(코드 서명 인증서가 없음). "추가 정보" → "실행"으로 진행하면 된다.

## 2. 첫 project 만들기

1. **File > New Project...** 를 선택한다.
2. 저장할 위치와 파일 이름(`*.gwbproj`)을 지정한다.
3. project 이름을 입력한다.

project를 열면 왼쪽 **Project Explorer**, 가운데 **Genome Map / Circular Map / Feature Table** 탭, 오른쪽 **Inspector**, 하단 **Jobs & Log / BLAST** 패널이 나타난다.

**Project Explorer로 record 정리하기**: 빈 공간을 우클릭하면 **New Folder...**로 폴더를 만들 수 있고, 폴더 안에 다시 하위 폴더를 만들 수도 있다(중첩 가능). Record나 폴더를 우클릭하면:
- **Move to Folder...**: 원하는 폴더(또는 "Project root")로 이동한다.
- **Rename Folder...** / **Delete Folder** (폴더를 지워도 안의 record와 하위 폴더는 삭제되지 않고 한 단계 위로 이동한다 — 폴더는 순수하게 정리용이라 실수로 데이터를 잃을 위험이 없다).
- **Delete Record...**: 확인 후 이 record와 그 안의 모든 annotation을 project에서 완전히 삭제한다(원본 파일은 영향받지 않는다). 되돌릴 수 없으니 확인 창의 내용을 확인할 것.

## 3. 파일 열기 (Import)

- **File > Import FASTA...**: `.fasta`, `.fa`, `.fna`, `.faa` 등(gzip 포함)을 연다. 여러 record가 있으면 모두 Project Explorer에 나타난다.
- **File > Import GenBank...**: `.gb`, `.gbk`, `.gbff` 등을 연다. 기존 annotation(gene, CDS, tRNA 등)이 함께 들어온다.
- **File > Import GFF3...**: `.gff3`를 연다. GFF3 파일에 `##FASTA` 구간이 없으면(annotation-only) 대응하는 서열 FASTA 파일을 선택하라는 창이 뜬다.

가져온 뒤 첫 record가 자동으로 선택되어 Genome Map에 표시된다.

## 4. Genome Map 조작 (마우스만으로)

- **마우스 휠**: 확대/축소. 커서 위치를 기준으로 확대된다.
- **Shift + 휠**: 좌우 이동(pan).
- **좌클릭 + 드래그**: 빈 공간에서 드래그하면 구간을 선택한다(하늘색으로 강조 표시).
- **feature 클릭**: 해당 feature가 선택되고, 오른쪽 Inspector와 Feature Table, Circular Map에 동시에 반영된다.
- **feature 더블클릭**: 해당 feature 범위로 확대한다.
- **feature 경계 근처 드래그**: 선택된 단일 구간 feature의 시작/끝 좌표를 조정한다(compound feature는 지원하지 않으며 안내 메시지가 뜬다).
- 상단 툴바: **Zoom In / Zoom Out / Fit Genome / Zoom to Selection** 버튼.
- 하단 **minimap**: 클릭하거나 드래그하면 그 위치로 이동한다.
- **Ctrl+C**: 드래그로 선택한 구간이 있으면 그 구간의 원시 염기서열을, feature를 클릭해 선택한 상태라면 그 feature의 생물학적 서열(strand/join 반영)을 클립보드로 복사한다. 동시에 그 구간은 아래 "구간을 새 record로 붙여넣기(Ctrl+V)"에서 쓸 수 있도록 내부적으로도 기억된다.

확대 수준에 따라 자동으로:
- 전체 genome을 한눈에 보는 최대 축소 상태: 밀도 그래프만 표시(개별 유전자 이름을 표시하기엔 너무 축소된 상태)
- 그보다 조금이라도 확대하면: 색상 strand 화살표(+가 오른쪽, -가 왼쪽)와 함께 유전자 이름(label)이 바로 나타난다 — 화면 폭에 비해 화살표가 너무 좁아 글자가 안 들어가는 경우에만 이름이 생략된다
- 세부 확대: 염기 문자(윗줄: 정방향, 아랫줄: 상보가닥), CDS라면 그 위에 번역된 amino acid도 표시

**Circular Map** 탭은 현재 record의 topology가 실제로 **circular**일 때만 활성화되고, circular record를 선택하면 자동으로 그 탭이 기본으로 열린다(선형 지도는 언제든 탭을 눌러 볼 수 있다). linear record에서는 원형으로 표시할 근거(원점)가 없으므로 이 탭 자체가 비활성화된다. Project Explorer에서 record를 우클릭하면 **Set Circular / Set Linear**로 topology를 바꿀 수 있다.

Circular Map에서도 마우스만으로 조작할 수 있다:
- **마우스 휠**: 확대/축소. 링의 고정된 중심이 아니라 **커서 위치를 기준으로** 확대되므로, 보고 있던 유전자가 확대 중에 화면 밖으로 밀려나지 않는다.
- **빈 배경 위에서 드래그**: 링을 회전시킨다(관심 있는 유전자를 원하는 각도로 돌려서 볼 수 있다). feature 위에서 드래그를 시작하면 대신 선택된다(기존 클릭 동작 유지).
- 다른 record를 선택하면 확대/회전 상태는 자동으로 초기화된다.
- **Ctrl+C**: 선택된 feature의 생물학적 서열을 클립보드로 복사한다.

Feature Table에서도 여러 행을 선택하고 **Ctrl+C**를 누르면 탭으로 구분된 텍스트(Label/Type/Start/End/Strand/Length/Gene/Product)로 복사되어 Excel 등에 바로 붙여넣을 수 있다.

Project Explorer에서 record나 폴더를 선택하고 **Delete** 키를 누르면 우클릭 메뉴의 삭제와 동일한 확인 절차를 거쳐 삭제된다.

**구간을 새 record로 붙여넣기(Ctrl+V)**: Genome Map이나 Circular Map에서 **Ctrl+C**로 구간(또는 feature)을 복사한 뒤, Project Explorer에서 붙여넣을 위치를 클릭하고 **Ctrl+V**를 누르면 그 구간만 잘라낸 새 record가 만들어져 project에 추가된다. 이때 그 구간 안에 완전히 포함된 annotation(gene, CDS 등)도 좌표가 새 record 기준으로 자동 재계산되어 함께 복사된다(구간 경계에 걸쳐 일부만 포함된 feature는 애매한 반쪽짜리 annotation이 되는 것을 막기 위해 복사되지 않는다). 붙여넣을 위치는:
- **폴더를 클릭한 상태**라면 그 폴더 안에 생성된다.
- **폴더 안에 있는 record를 클릭한 상태**라면 같은 폴더 안에 생성된다.
- 아무것도 선택하지 않았거나 폴더에 속하지 않은 record를 선택한 상태라면 project 최상위에 생성된다.

## 5. 유전자/qualifier로 찾기 (Find)

**Edit > Find Feature...** (Ctrl+F)로 검색 창을 연다. project 안의 모든 record를 대상으로 gene, locus_tag, product, note를 비롯한 모든 qualifier 값을 부분 일치로 검색한다. 결과 목록에서 항목을 더블클릭하거나 Enter를 누르면 해당 record로 전환되고 Genome Map이 그 feature로 확대되며 Inspector에도 선택된다.

## 6. 수동 annotation 만들기

1. Genome Map에서 원하는 구간을 마우스로 드래그해 선택한다.
2. 선택 영역에서 **우클릭 → Add Annotation...** 을 선택한다(또는 **Annotation > Add Feature...** 메뉴, 이 경우 좌표를 직접 입력).
3. 대화상자에서:
   - **Start/End**: 드래그한 좌표가 이미 채워져 있다(1-based).
   - **Strand**: +/-
   - **Feature type**: CDS, gene, tRNA 등(직접 입력도 가능)
   - **Multiple segments (join)** 체크박스: 체크하면 여러 구간을 입력해 하나의 compound(join) feature를 만들 수 있다(intron이 있는 유전자 등). 구간을 어떤 순서로 입력해도 strand에 맞는 생물학적 순서로 자동 정렬된다. 이때는 각 구간마다 **Fuzzy start (<) / Fuzzy end (>)** 체크박스가 표에 함께 나타난다.
   - **Fuzzy start (<) / Fuzzy end (>)** 체크박스(join이 아닐 때는 좌표 옆에 표시됨): GenBank의 `<`/`>` 표기처럼 "정확한 시작/끝 위치를 모르거나 표시된 좌표 너머까지 이어진다"는 뜻이다. contig 경계에서 잘린 유전자 등에 사용한다.
   - gene/product/note/transl_table 입력
   - **Preview** 버튼으로 길이, translation, 시작/종료 코돈, 내부 stop codon 여부를 미리 확인한다.
4. **OK**를 누르면 즉시 저장된다(별도의 "Save" 없이도 project 파일에 즉시 기록된다).

## 7. 기존 annotation 확인/수정

1. Genome Map, Circular Map, Feature Table 중 어디서든 feature를 클릭한다.
2. 오른쪽 **Inspector**에 type, strand, 좌표, 공통 qualifier(gene/locus_tag/product/note/db_xref/inference), 추출된 nucleotide/translation, validation 경고, provenance가 표시된다.
3. 값을 직접 수정한다. 공통 6개 필드 외의 qualifier는 **All other qualifiers** 표에서 **Add Qualifier / Remove Selected**로 자유롭게 추가·삭제한다(multi-value 가능).
4. **여러 구간(join/compound) feature**를 열면 **Multiple segments (join)** 체크박스가 자동으로 켜지고 구간 목록이 표에 나타난다. 표에서 좌표를 직접 수정하거나 **Add Segment/Remove Selected**로 구간을 추가/삭제할 수 있다 — 어떤 순서로 입력해도 strand에 맞게 자동 정렬된다. 체크박스를 끄면 단일 구간으로 축소된다(의도적으로 그렇게 하려는 경우에만 사용).
5. **Fuzzy start (<) / Fuzzy end (>)** 체크박스로 기존 feature의 fuzzy 경계도 켜고 끌 수 있다(join 모드에서는 구간별로 표의 체크박스로 조정).
6. **Apply**를 누르면 저장되고, **Revert**를 누르면 마지막 저장 상태로 되돌린다.

## 8. 선택 영역으로 할 수 있는 것 (우클릭 메뉴)

Genome Map에서 구간을 드래그 선택한 뒤 우클릭하면:

- **Add Annotation...**: 위 5번 참고
- **Run BLAST...**: 아래 9번 참고
- **Copy Sequence / Copy Reverse Complement**: 클립보드로 복사
- **Translate (+ strand) / Translate (- strand)**: 번역 결과를 바로 보여준다
- **Export Selection as FASTA...**: 선택 구간만 FASTA로 저장
- **Extract Selection as New Record...**: 선택 구간을 새 record로 project에 추가한다(원본은 바뀌지 않음). 구간 안에 완전히 포함된 annotation도 함께 복사된다. **Ctrl+C** 후 Project Explorer에서 **Ctrl+V**를 누르는 것과 동일한 결과이며, 차이는 붙여넣을 폴더를 미리 선택해 둘 수 있는지 여부뿐이다.
- **Reverse Complement Whole Record as New Record...**: 현재 record 전체의 reverse complement를 새 record로 추가한다

## 9. 여러 feature를 한 번에 편집하기 (Batch)

Feature Table 탭에서 여러 행을 **Ctrl/Shift-클릭**으로 다중 선택한 뒤 우클릭하면:

- **Batch Edit Qualifiers...**: **Set**(기존 값을 덮어씀) / **Add**(기존 값 유지하고 추가, multi-value qualifier에 적합) / **Remove**(해당 qualifier 삭제, 원래 없던 feature는 건드리지 않음) 중 선택해 선택된 모든 feature에 한 번에 적용한다.
- **Apply Template...**: 저장해 둔 annotation template(아래 참고)의 type과 qualifier를 선택된 모든 feature에 한 번에 적용한다. Template에서 비워둔 필드는 기존 값을 지우지 않는다.
- **Run BLAST on Selected...**: 하단 BLAST 패널에서 고른 database/program/parameter로 선택된 모든 feature를 순서대로 검색한다(각 feature 고유의 strand·join 구조를 반영해 실제 생물학적 서열로 query를 만든다). 끝나면 feature별 최상위 hit 요약 표가 뜬다 — 행을 선택하고 **Review & Apply Selected...**를 누르면 단일 BLAST와 똑같이 미리보기 대화상자를 거쳐야만 annotation이 적용된다(자동 적용 없음). 검색 도중에는 BLAST 패널의 **Cancel Job**으로 중단할 수 있다.

**Batch Edit Qualifiers...**와 **Apply Template...**는 **Undo 한 번**으로 전체를 되돌릴 수 있다(여러 feature가 바뀌어도 하나의 실행 취소 단계로 처리됨). BLAST는 annotation 적용 자체가 개별 확인을 거치므로 각 적용 건이 별도의 undo 단계다.

**Annotation template**은 `Add Annotation...` 대화상자에서도 사용할 수 있다: type과 gene/product/note/transl_table을 입력한 뒤 **Save as Template...**로 이름을 붙여 저장하면, 다음에 새 feature를 만들 때 **Template** 드롭다운에서 선택해 즉시 값을 채울 수 있다. 필요 없어지면 **Delete Template**로 지운다. Template은 project가 아니라 사용자 컴퓨터 전체에 저장되어 다른 project에서도 재사용된다.

## 10. Undo/Redo

**Edit > Undo / Redo** (Ctrl+Z 상당). feature 생성/수정/삭제가 대상이다. project를 닫으면 undo 기록은 초기화된다(단, project 파일 자체는 매 작업마다 즉시 저장되어 있으므로 데이터가 사라지지는 않는다).

## 11. BLAST 설치 및 사용

### 9.1 BLAST 설치 확인

**BLAST > BLAST Setup...** 을 클릭한다. 자동으로 PATH와 일반적인 설치 위치에서 `makeblastdb`, `blastdbcmd`, `blastn`, `blastp`, `blastx`, `tblastn`을 찾는다. 없으면 "BLAST+ bin directory"에 직접 경로를 입력하고 **Detect**를 누른다.

이 프로그램은 BLAST+ 실행파일을 포함하지 않는다. 대화상자의 **Download & Install BLAST+ (official NCBI build)** 버튼을 누르면 NCBI 공식 배포처에서 최신 Windows용 배포판(~140MB)을 내려받아 체크섬을 검증하고 `%LOCALAPPDATA%/DNAvigator/tools`에 설치한 뒤 자동으로 재탐지한다(관리자 권한 불필요, 다운로드 중 진행률 표시 및 취소 가능). 수동으로 설치하고 싶다면 공식 배포처(https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/)에서 내려받아 경로를 등록해도 된다. 자세한 내용은 `docs/BLAST_SETUP.md` 참고.

### 9.2 Custom database 만들기

하단 **BLAST** 패널에서 **Create Database...** 를 클릭하고 source FASTA(nucleotide 또는 protein), 이름을 지정한다. ID에 문제가 있는 문자(`|` 등)가 있으면 자동으로 안전한 ID로 변환하고 원래 ID와의 매핑을 기록한다.

### 9.3 BLAST 실행

특정 구간만 검색하려면: Genome Map에서 구간을 선택하고 우클릭 → **Run BLAST...**

**전체 contig/서열을 검색하려면**(예: WGS 어셈블리 전체를 resistance gene database에 대조): 매번 구간을 손으로 드래그해서 선택할 필요 없이, Project Explorer에서 record를 선택한 뒤 **BLAST > Run BLAST on Whole Record...** 를 누르면 그 record 전체 서열이 바로 쿼리로 설정된다.

두 방법 모두 이어지는 단계는 동일하다:

1. (위 두 방법 중 하나로 쿼리를 설정한다.)
2. 하단 BLAST 패널에서 database, program(자동 제안됨), e-value, max target sequences 등을 확인/조정하고 **Run BLAST** 클릭.
3. 실행 중에는 **Cancel Job** 버튼이 활성화된다 — 잘못된 database를 선택했거나 너무 오래 걸리면 눌러서 즉시 중단할 수 있다(database 생성 중에도 동일하게 사용 가능). 취소하는 동안에는 새 job을 시작할 수 없다.
4. 결과 표에서 hit을 클릭하면 오른쪽에 HSP alignment(identity, coverage, e-value, bit score, aligned sequence)가 나타난다.

### 9.4 BLAST 근거로 annotation 적용

hit을 선택한 뒤 **Apply as Annotation...** 을 클릭한다. 대화상자에서:
- 매핑된 genome 좌표와 strand를 확인한다(자동 계산됨)
- feature type을 선택한다
- 어떤 정보를 복사할지 선택한다: product(subject title에서), note(BLAST 근거 요약, 기본 선택됨), db_xref(subject ID). **product는 기본적으로 선택되어 있지 않다** — plain FASTA title을 무비판적으로 product로 확정하지 않기 위함이다.

**OK**를 눌러야만 annotation이 만들어진다 — top hit이 자동으로 적용되는 일은 없다. 적용된 annotation은 사용한 BLAST 프로그램/버전/database/subject/identity/e-value가 함께 기록되며(Inspector의 Provenance), database를 나중에 삭제해도 이 근거 정보는 project에 남는다.

## 12. Export

- **File > Export GenBank...**: 내부적으로 임시 파일에 쓴 뒤 다시 읽어서 원본과 의미적으로 동일한지 검증하고, 문제가 없을 때만 최종 경로에 기록한다(원본 파일 덮어쓰기 없음).
- **File > Export GFF3...**: 서열을 같은 파일에 포함(`##FASTA`)할지 별도 파일로 둘지 물어본다.
- **File > Export Nucleotide FASTA...** / **Export Protein FASTA (protein records)...** / **Export Protein FASTA (CDS translations)...** / **Export FFN (CDS nucleotide)...** / **Export Feature Table CSV...**

## 13. Feature 색상 커스터마이징과 이미지 내보내기

**View > Feature Colors...**를 열면 feature 타입별(CDS, gene, tRNA 등) 색상을 바꿀 수 있다.

- 색상 스와치를 클릭하면 색상 선택 대화상자가 뜬다.
- **Add Type...**으로 기본 목록에 없는 타입(예: ncRNA, terminator)의 색도 지정할 수 있다.
- 행별 **Reset** 버튼 또는 **Reset All to Defaults**로 기본값으로 되돌릴 수 있다.
- 설정한 색은 project가 아니라 사용자 전역으로 저장되어(`%LOCALAPPDATA%\DNAvigator\feature_colors.json`) 다른 project를 열어도 그대로 적용된다.

**View > Export View as Image...**로 현재 보고 있는 Genome Map, Circular Map, Alignment View 탭을 그림 파일로 저장할 수 있다(Feature Table 탭에서는 사용할 수 없음).

- **PNG**를 선택하면 해상도 배율(1x/2x/3x/4x)을 물어본다 — 논문이나 인쇄용으로 쓰려면 3x 이상을 권장한다.
- **SVG**를 선택하면 벡터 파일로 저장되어 어떤 크기로 확대해도 깨지지 않는다.
- feature 화살표는 은은한 그라데이션으로 그려져 화면 스크린샷보다 또렷하게 인쇄된다.

## 14. Alignment View (여러 서열 비교)

이미 정렬(align)된 서열 여러 개를 한 화면에서 비교하고, 서로 다른 부위를 한눈에 확인할 수 있는 기능이다. 자체적으로 정렬을 수행하지는 않으며, 이미 MSA(Multiple Sequence Alignment) 프로그램으로 정렬을 마친 파일을 불러와 보여준다.

**File > Import Alignment...**로 정렬 파일을 연다. FASTA(gap 문자 `-` 포함), Clustal(`.aln`), Stockholm(`.sto`), PHYLIP(`.phy`), NEXUS(`.nex`), MSF 형식을 지원하며, 확장자로 형식을 먼저 판별하고 실패하면 다른 형식들도 순서대로 시도한다. Record와 마찬가지로 Project Explorer에 나타나고, 폴더로 정리하거나 이름 변경/삭제할 수 있다(각각 우클릭 메뉴 또는 Delete 키).

Project Explorer에서 정렬 항목을 클릭하면 **Alignment View** 탭이 자동으로 열린다:

- 맨 위에는 **Consensus**(각 위치에서 가장 많이 나타나는 염기/아미노산) 행이 고정 표시된다.
- 그 아래 **conservation bar**는 위치별로 서열들이 얼마나 다른지를 막대 높이로 보여준다 — 막대가 높을수록(붉을수록) 그 부위에서 서열 간 차이가 크다는 뜻이라, 확대하지 않고도 어디를 봐야 할지 바로 알 수 있다.
- 각 서열 행은 염기/아미노산마다 색이 칠해지고, **consensus와 일치하는 칸은 옅게, 다른 칸은 진하게** 표시되어 차이가 나는 부위가 저절로 도드라진다.
- 충분히 확대하면 칸 안에 글자(염기/아미노산)도 함께 표시된다.
- **마우스 휠**로 좌우(열) 확대/축소, **Shift + 휠**로 좌우 이동. 서열이 화면보다 많으면 오른쪽 스크롤바로 위아래 이동한다.
- 툴바의 **Zoom In / Zoom Out / Fit Whole Alignment** 버튼으로도 조작할 수 있다.

**View > Alignment Colors...**(Alignment View 탭이 열려 있을 때 활성화)로 염기/아미노산별 색을 직접 지정할 수 있다 — 방식은 Feature Colors와 동일하며(색상 스와치 클릭, Reset, Add Residue...), 뉴클레오타이드용과 아미노산용 팔레트가 서로 분리되어 저장된다(`%LOCALAPPDATA%\DNAvigator\alignment_colors.json`).

## 15. Project 동시 열기 / 비정상 종료

같은 project 파일을 다른 DNAvigator 창(또는 이전에 비정상 종료된 세션)이 이미 열고 있으면, **Open Project**시 알림이 뜨고 **읽기 전용으로 열기** 또는 **강제로 편집 모드로 열기**(다른 인스턴스가 실제로 열려있지 않다고 확신할 때만) 중 선택할 수 있다.

## 16. 문제 해결

- **프로그램이 시작 시 콘솔 없이 조용히 종료된다**: `%LOCALAPPDATA%\DNAvigator\logs`의 로그 파일을 확인한다.
- **`DNAvigator.exe --self-test`**: 핵심 구성요소(쓰기 가능한 사용자 폴더, SQLite, FASTA 코덱, Qt) 상태를 점검한다. 결과는 콘솔과 `%LOCALAPPDATA%\DNAvigator\last_self_test_output.json`에 모두 기록된다.
- **`DNAvigator.exe --diagnostics`**: 버전, OS, Python/Qt/Biopython 버전 등을 JSON으로 출력한다.
- BLAST 관련 오류는 `docs/BLAST_SETUP.md`의 "일반 오류와 해결" 참고.
