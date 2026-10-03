# PanelSearch nanbyo 実装分析

調査日：2026-10-03。対象：`G:\visualstudio_code_workspace\pubcasefinder_pcf`。
本資料は操作ガイドの根拠・構成を記録する。ソース一覧の SHA256 で調査時の内容を識別できる。
管理者・Curator・Reviewer の storage_state は更新済みで、ファイルの存在とサイズを確認した。ただし実行環境が Playwright の駆動子プロセス起動を拒否したため、今回それらを使ったログイン画面の再撮影・操作確認は完了していない。既存 E2E 画像は今回の動作成功を証明するものではない。

## 1. 構成とデータの流れ

Flask `app.py` が HTML と JSON API を提供する。ページは Jinja テンプレート、jQuery 系スクリプトが画面部品と非同期読込を担当する。MySQL のデータ操作・集計は主として `utils/api_psn.py`、Ontology 更新は `utils/api_psn_ontology.py` に集約される。

一覧の `vgp_panel_list.js` と `jquery.vgp.js` は分類ツリー、検索状態、カード、遺伝子・表現型展開を組み合わせる。パネル詳細の `vgp_panel_detail.js` はエンティティ、外部評価、ユーザーレビュー、論文、版比較・投稿者の各表示を構成する。エンティティ詳細の `vgp_panel_entity_detail.js` と `vgp_user_panel_entity.js` は定義・レビュー・コメント・履歴を表示する。`jquery.review.js` がタイプ別の投稿フォームと確認段階を作る。

管理画面は `admin_layout` を共有するが、ユーザー、グループ、活動、担当活動、認証、プロフィール、自己レビュー、メールは別モジュールである。メール SMTP 画面は閲覧専用。`admin_statistics` は `not yet` のテンプレートであり、ページルートに接続されていない。

## 2. ページと入口

ガイドは以下の独立 13 画面を対象とする。タブ、ダイアログ、サイドパネルは対応章内に含める。API・共有ページ・別名は独立画面数に加算しない。

|画面|主な対象|主な機能|
|---|---|---|
|panel_list|公開|疾患ツリー、Panel/Gene 検索、並べ替え、Show More、カード、TSV|
|panel_detail|公開・担当者|4タブ、根拠、論文、版比較、Add Entity/Review|
|panel_entity_detail|公開・担当者|定義、レビュー、コメント、履歴、遺伝子情報|
|ontology|公開・Admin|DB版参照、Turtleローカル解析、比較、確定更新|
|admin_user|Admin|申請処理、状態変更、本人情報、管理者権限|
|admin_group|Curator/Admin|所属メンバー、役割、グループ、担当パネル|
|admin_group_activity|Admin|メンバー追加・削除・役割変更履歴|
|admin_activity|ログイン|パネル・版・エンティティ・期間別の変更前後|
|admin_incharge|Curator/Admin|担当の最新活動、Curate、確認済み・未読|
|admin_authentication|Admin|認証イベント、結果、理由、user-Agent|
|admin_profile|ログイン|本人情報、Edit/Save/Cancel、退会確認|
|admin_review|ログイン|自分のレビュー・コメント参照、詳細へのリンク|
|admin_mail|Admin|ログ検索・詳細・再送、テンプレート編集、SMTP参照|

`/panelsearch_nanbyo_admin` と `/panellist_nanbyo_admin` はユーザー管理への別名。共通ヘッダー、入力部分テンプレート、エラー、利用規約などの補助要素もガイドで説明する。

## 3. 権限モデル

Admin はサービス全体の管理者。Reviewer/Curator は「ユーザー → 有効グループ → 役割 → グループの担当パネル」の関連を通してパネル別に決まる。ページのメニュー表示と API の権限条件は分けて確認する。たとえば活動ページのルートはログインを条件とする。

Review の編集・削除は元の作成者、Admin、対象パネルの Curator を基準に確認する。Comment はサーバーの記録から所有者を確認する。Add Comment のログイン条件と、Add Review の対象パネル役割条件は異なる。Definition の管理は Admin または対象パネルの Curator。担当活動の確認 API も担当範囲を検証する。グループのパネル関連付けと作成・名称変更・削除は Admin の操作であり、Curator のメンバー管理とは異なる。

## 4. エンティティと根拠

エンティティは Gene=1、STR=2、Region=3。動的フォームで Gene はシンボルと Phenotype、STR はシンボルと名称、Region は名称の必須検査がある。座標・反復数・領域スコア等の表示はタイプ別。Region Haploinsufficiency Score が STR の表示項目に含まれる点は現行実装上の差異としてガイドに明記した。静的入力テンプレートの項目をそのまま動的フォームの機能と見なさない。

Review は利用者の評価と根拠。Definition はキュレーションされた定義。外部参照による自動レビューも別情報源として扱う。Add Entity はレビュー登録の入口であって Definition の直接確定ではない。Rating は実装に10区分があるが、コードから採点基準や臨床閾値を補ってはいない。

編集時には同時更新の検査があり、古い Review を更新しようとすると409の競合応答になる。削除は有効性・活動記録・版との関連を伴う。コメントのライフサイクルは Review の change 活動として追跡する。担当活動の確認は curator_check_history を使い、レビューの評価承認とは別の状態である。

## 5. 版管理とデータテーブル

`panelsearch_nando_panel`、`panel_version` がパネルと版を保持する。`entity`、`entity_type`、`entity_rating`、`entity_mode_of_inheritance` がエンティティと評価・遺伝形式、`entity_review`、`entity_review_comment` が利用者の投稿を保持する。`entity_panel_version`、`entity_review_panel_version`、`user_activity_panel_version`、`panel_change_panel_version` は版との関連を表す。

分類には `panel_hierarchy`、`panel_descendant`、`panel_upstream_trace`、`panel_version_root_trace` が使われ、上位経路は単一路とは限らない。`ontology`、`panel_snapshot`、`panel_change` が Ontology とスナップショット・差分に関係する。担当は `group`、`group_user`、`group_panel`、活動は `group_activity`、`user_activity`、`curator_check_history` で記録する。これは SQL 定義と使用箇所に基づく論理説明であり、全関係に DB 外部キー制約が設定されているとの主張ではない。

## 6. Ontology 更新

ブラウザーで N3 パーサーにより Turtle を解析し、使用・obsolete・未使用のツリーや表を生成する。拡張子候補に .rdf や .owl があっても、任意の RDF/XML を受け付けるとの意味ではない。現行版と MD5 を照合し、アップロードコメントを確認する。確定処理は Admin の API で再解析・関連データ取得と階層構築を行い、トランザクションで保存する。ブラウザーとサーバーで循環参照等の検査がある。ローカル解析とサーバー確定更新を同一操作と扱わない。

## 7. エクスポートとメール

パネル詳細 TSV はパネルに読み込まれた定義・自動レビュー・利用者レビューの情報源を出力する。画面の文字フィルターが TSV を絞るわけではない。12列：panel_disease_id、panel_disease_name、reference_nando_id、disease_name_en、disease_name_ja、ncbi_gene_id、gene_symbol、classification、source、source_url、moi_en、moi_ja。全パネル TSV は `/static/data/panelsearch_nanbyo/all_panel.tsv` の用意済みファイル。

メールログは Pending/Sent/Failed を検索し、詳細でエラーを確認できる。Resend は外部送信を発生させる。テンプレートは編集・確認保存できるが SMTP 入力は無効化され、編集ボタンがコメントアウトされている。画面説明のためにメール再送やユーザー権限変更は実行していない。

## 8. 検証の範囲と再現

ローカルのルート・テンプレート・JS・Python・SQL・E2Eテストを照合し、公開画面で一覧、ACTA1検索、パネル詳細、版関連、エンティティ詳細、Ontology を閲覧した。添付画像は本次公開画面と既存 E2E の混在で、出所は図注とCSVに明示する。既存画像のファイル更新日は撮影日時の保証ではない。

実行環境の Windows 子プロセス起動で WinError 5 / EPERM が発生したため、更新済み3役の認証状態を使った再撮影は未完了。権限の修正後は付属の `refresh_screenshots.py` をリポジトリの E2E 仮想環境の Python で実行できる。実際の更新APIはブロックし、閲覧・検索の読込だけを許可する。操作テストの全面成功は報告していない。

APIルート一覧は AST から `nanbyo` を含むルートのパス・HTTPメソッド・関数・テンプレート・主要API呼出しを抽出した。関数一覧は共通認証を含むバックエンドの定義を列挙する。CSVの行番号は調査時ソースに対応し、将来の更新で変わる。

## 9. 画面ごとの機能対応

### 01. はじめに

PanelSearch nanbyo は、難病の疾患分類から遺伝学的検査用パネルを探し、遺伝子などのエンティティ、根拠資料、評価、レビューを参照するためのサービスです。本書は閲覧者、Reviewer、Curator、Admin が、それぞれの画面で何を確認し、どの順序で操作するかを説明します。まず疾患または遺伝子を検索し、パネル詳細からエンティティ詳細へ進みます。投稿や定義の管理には対象パネルの権限が必要です。

- **閲覧の流れ**：パネル一覧 → パネル詳細 → エンティティ詳細 → 根拠・レビュー・履歴の確認。
- **レビューの流れ**：対象パネルの Reviewer または Curator、あるいは Admin でログイン → Add Review → 入力 → 確認 → 確定。
- **キュレーションの流れ**：担当アクティビティ → 変更履歴 → Curate → Entity Definition → 確認処理。
- **管理の流れ**：ユーザーの承認 → グループと担当パネルの設定 → 活動・認証・メールの確認。
- **本書の操作例**：先天性ミオパチー NANDO:1200477 と ACTA1 NCBI Gene ID 58 を使用します。件数、日付、評価は例示画面の値です。

参照：`app.py`, `tests/e2e_psn/README.md`

### 02. 利用者の役割と権限

Admin はサービス全体を管理します。Reviewer と Curator は、グループ内の役割とそのグループに登録されたパネルによって担当範囲が決まります。同じ利用者でも、パネルが変わると表示される操作が変わる場合があります。

- **未ログイン**：パネル一覧、パネル詳細、エンティティ詳細、Ontology の閲覧。レビュー登録・編集はできません。
- **ログイン済み利用者**：プロフィール、自分のレビュー、活動ページへアクセス可能。レビューへの Add Comment はログインを条件とする操作です。
- **対象パネルの Reviewer**：対象パネルへの Add Entity / Add Review。自分が作成した Review / Comment の編集・削除。
- **対象パネルの Curator**：担当パネルの Entity Definition を追加・変更・削除。担当パネル内の他者の Review / Comment も管理可能。
- **Admin**：全パネルの定義・レビュー管理、ユーザー管理、グループ作成・変更・削除、グループへのパネル関連付け、認証ログ、メール管理、Ontology の確定アップロード。
- **グループの有効性**：無効化されたグループの関連だけでは Curator の操作権限を得られません。
- **画面と API**：ボタンが見えることだけで権限が確定するわけではありません。サーバーが所有者、対象パネル、所属・役割を検証します。

参照：`app.py`, `utils/api_psn.py`, `static/js/panelsearch_nanbyo/admin.js`

### 03. 共通ヘッダーとログイン

画面上部のロゴ、Service、言語、Log in またはユーザーメニューから、サービス移動と言語・アカウント操作を行います。

- **ロゴ**：PanelSearch nanbyo のパネル一覧へ戻ります。
- **Service**：別サービスへの移動メニューを開きます。Nanbyo の投稿権限は Nanbyo 用アカウントと担当設定で判定されます。
- **日本語 / English**：表示言語を変更します。パネル名の日本語・英語やふりがなの表示、入力候補などに影響します。
- **Log in**：ログインダイアログを開きます。Google の Log in と Sign up が表示されます。
- **Sign up**：Nanbyo の登録先へ進みます。申請・認証・承認などのアカウント状態は管理画面で扱います。
- **ユーザーメニュー**：ログイン後のプロフィール、My page や管理ページへの導線、ログアウトを利用します。表示項目は権限によって異なります。
- **ログアウト**：セッションを終了します。ログインを必要とするページでは再ログインが必要になります。
- **パンくずリスト**：上位分類やパネルへ戻ります。疾患分類には複数の上位経路が存在する場合があります。
- **Go to top**：長いページをスクロールした後に、ページ上部へ戻ります。

参照：`static/js/common-header-auth-panelsearch_nanbyo.js`, `templates/common_header.html`, `templates/panelsearch_base.html`

### 04. パネル一覧

左側の Tree で対象の疾患分類を選び、右側で疾患・パネルのカードを確認します。最初の表示では遺伝学的検査用パネルが選ばれます。すべての疾患を探すときは All、未指定疾患群を探すときは対応する分類を選択してください。

- **Tree**：All、遺伝学的検査用パネル、遺伝学的検査用パネル未指定疾患群から範囲を選択。枝を展開・折りたたみ、ノードをクリックすると一覧を更新します。括弧内の数は分類に属する件数です。
- **undo / redo**：一覧の検索語、対象、表示件数やツリー選択など、保存された閲覧状態を戻す・進める操作です。レビュー投稿の取消機能ではありません。
- **Panel / Gene**：検索対象を切り替えます。Panel はパネル名称・同義語等、Gene は遺伝子シンボル・NCBI Gene ID の対応でパネルを探します。切替時には検索文字を保持して再検索します。
- **検索入力**：文字を入力すると検索を実行します。検索語を空にすると、現在のツリー範囲の一覧に戻ります。入力中の読み込みが終わるまで待ちます。
- **Per page**：一度に表示する件数を変更します。下部の Show More は続きのカードを追加表示します。
- **Panel / Panel genes の列見出し**：パネル名や遺伝子数による並べ替えを行います。矢印で昇順・降順を確認します。
- **Updated**：一覧の更新日を確認します。本書作成日とは異なります。
- **All panels**：用意された全パネル TSV をダウンロードします。現在の検索で見えているカードだけを出力する機能ではありません。

参照：`templates/panelsearch_nanbyo_panel_list.html`, `static/js/panelsearch_nanbyo/vgp_panel_list.js`, `static/js/panelsearch_nanbyo/jquery.vgp.js`, `utils/api_psn.py`

### 05. 一覧カードの各機能

カードには疾患名、英語名、告示番号、概要、外部資料、遺伝子数、Clinical features の件数が表示されます。カード左側のアイコンと下部の展開項目を使うと、一覧を離れずに関連情報を確認できます。

- **疾患名**：パネル詳細へ進みます。日本語名にふりがなが表示される場合があります。
- **概要 / Show more**：長い概要の続きを表示します。告示番号や外部リンクはデータが存在する場合に表示されます。
- **概要、診断基準等**：厚生労働省などの資料を開きます。
- **臨床調査個人票・医療意見書**：対応する文書を開きます。
- **難病情報センター / NanbyoData / NANDO / Orphanet / OMIM**：元資料・識別子に対応する外部ページへ進みます。カードに存在するリンクを使用してください。
- **download アイコン**：そのパネルのデータを TSV として取得します。All panels の一括ファイルと使い分けます。
- **file_copy アイコン**：パネル概要データを整形 JSON でクリップボードにコピーします。遺伝子名だけをコピーする機能ではありません。
- **ツリーのアイコン**：そのパネルの上位経路を左 Tree に表示して所在を確認します。
- **Genes Show(n)**：遺伝子一覧を展開します。必要なデータを取得して表を作ります。再度操作して折りたたみます。
- **Clinical features Show(n)**：分類ごとの臨床特徴を表で展開します。再度操作して折りたたみます。
- **Show(0)**：対応データがないことを表します。0 件の場合は通常、詳細領域を開きません。

参照：`static/js/panelsearch_nanbyo/jquery.vgp.js`, `static/js/panelsearch_nanbyo/jquery.vgp_collapse_panel.js`

### 06. パネル詳細の概要

パネルの疾患情報、収録エンティティ、担当評価、各レビュー、資料、バージョンをまとめて確認する画面です。表示名に Panel genes が残っていますが、エンティティの種別は Gene、STR、Region を扱います。

- **疾患名 / パンくず / Tree**：現在のパネルと上位分類を確認し、他のパネルへ移動します。
- **Latest version / Previously version**：現在と直前のパネル版を確認します。表示には上位の検査用パネル名を伴う版番号が含まれる場合があります。
- **Summary Hide / Show**：告示番号、Definition、外部 Link などの概要表を折りたたみ・再表示します。
- **Show reviewers**：Reviewers タブへ移動します。括弧内は投稿した利用者数です。
- **Panel genes**：エンティティと評価・資料の一覧を表示します。
- **Version comments**：版の変更理由を時系列で参照します。
- **Reviewers**：投稿者の一覧と各人の Review 件数を参照します。
- **Version comparison**：2 つの版のエンティティと評価の差を比較します。
- **Download**：この詳細画面で取得した根拠・Review 等を TSV にします。フィルターで非表示にした行だけを除外する出力ではありません。

参照：`templates/panelsearch_nanbyo_panel_detail.html`, `static/js/panelsearch_nanbyo/vgp_panel_detail.js`, `app.py`

### 07. Panel genes の表と評価

表では、エンティティごとに Source Panel、Curator Rating、Reviewer/Reference ratings、Papers を確認します。同じ遺伝子でも参照される疾患や情報源が異なる行があります。評価は出所と併せて読み、票数と根拠の内容を区別してください。

- **Entities 件数と Filter entities**：エンティティ名で絞り込みます。ACTA1 などを入力すると一致行が残り、入力を空にすると解除します。
- **Entity**：Gene、STR、Region の識別名。遺伝子名のボタン・ポップアップで遺伝子情報を確認します。Source Panel 内の疾患リンクから、その組合せのエンティティ詳細へ進みます。
- **Source Panel**：そのエンティティの根拠を持つパネルと階層経路を確認します。現在表示中のパネル名と異なる場合があります。
- **Curator Rating**：Entity Definition に由来する担当評価を確認します。存在しない評価は No rating 等として扱われます。
- **Reviewer ratings**：利用者 Review の評価分布と件数を確認します。Show(n) を開くと投稿者や疾患、遺伝形式、評価の詳細表を確認できます。
- **Reference ratings**：外部参照に基づく評価の分布・件数を確認します。Show(n) で出所、疾患、評価などを表示します。
- **Papers**：件数がある場合に展開し、Title、Journal、Date、Source と元論文へのリンクを確認します。論文表にも並べ替えやページ送りがあります。
- **列見出し**：並べ替え可能な見出しをクリックして昇順・降順を切り替えます。
- **評価の凡例と ?**：各 Rating の色や表記を確認します。色だけでなく評価名と情報源を読みます。
- **Add Review / Add Entity**：権限を持つ利用者に投稿ボタンが表示されます。次章の入力・確認操作へ進みます。

参照：`static/js/panelsearch_nanbyo/vgp_panel_detail.js`, `static/js/panelsearch_nanbyo/utils.js`

### 08. Rating の表記

実装には以下の 10 区分があります。ここでは画面の読み方として日本語の意味を示します。これらは疾患とエンティティの関連に対する区分であり、個々の患者の診断結果や特定変異の病原性判定を示す欄ではありません。

- **Definitive**：確立した関連として表示される区分。
- **Strong**：強い関連を示す区分。
- **Moderate**：中程度の関連を示す区分。
- **Supportive**：関連を支持する根拠として表示される区分。
- **Limited**：限定的な根拠として表示される区分。
- **Disputed**：関連について異議・議論がある区分。
- **Refuted**：関連が否定された区分。
- **Animal**：動物の根拠に関する区分。
- **No known**：既知の関連がない区分。
- **No rating**：評価が付いていない区分。

参照：`static/js/panelsearch_nanbyo/utils.js`, `sql/panelsearch_nando_entity_rating.sql`

### 09. 版コメント 投稿者一覧 版比較

3 つのタブを使って、いつ変更されたか、誰がレビューしたか、どのエンティティや評価が変わったかを順に確認します。

- **Version comments**：日付、コメント、関連する版番号を読みます。定義追加・削除などの変更理由が記録されます。
- **Reviewers 一覧**：名前、Affiliation、Reviews written を確認します。Total は利用者数であり、Review の総数とは異なります。
- **Reviews written の件数ボタン**：その Reviewer が投稿した Review の一覧を開きます。遺伝子、評価、疾患、遺伝形式、リンク等を確認します。
- **Version comparison の選択欄**：比較元と比較先の 2 版を選びます。初期値は直近の版を使用します。
- **Added / Removed / Rating changed**：追加、削除、評価変更を集計表示します。差がない行はハイフン等で表示されます。
- **Total genes と件数**：比較した版の収録数の変化を確認します。エンティティ名の Filter で差分表を絞り込めます。
- **比較フィルター解除**：入力を空にして全行へ戻します。版の変更と文字による行絞り込みは別操作です。

参照：`static/js/panelsearch_nanbyo/vgp_panel_detail.js`, `utils/api_psn.py`

### 10. Add Entity と Add Review

Add Entity は対象パネルにないエンティティを選んで Review を登録する入口です。Add Review は既存エンティティに対する Review の入口です。どちらも同じレビュー入力機構を使用し、Entity Definition を直接確定する機能とは区別されます。

- **Add Entity**：未登録候補から Gene 等を選んでレビュー入力を開始します。候補一覧から選択し、表示文字を入力しただけで済ませないようにします。
- **Add Review**：行に対応するパネル・エンティティが初期入力されます。投稿先の疾患を確認します。
- **Rating**：評価候補を選びます。No rating の初期値を、そのまま意図した評価と誤認しないよう確認します。
- **Entity Type**：Gene、STR、Region を選択します。タイプに応じて表示される入力欄が変わります。
- **Gene Symbol**：検索候補から遺伝子を選びます。Gene と STR では必要です。
- **Entity Name**：STR と Region の名称を入力します。Gene は選択したシンボルを基準に扱われます。
- **Phenotype**：対応する疾患候補を選択します。Gene のレビューでは選択が必要です。実装では NANDO の対象疾患を入力候補として使用する場面があります。
- **Mode Of Inheritance**：遺伝形式を階層候補から選択します。複数の該当する形式を選べる構成です。
- **Publications**：PMID または DOI を入力します。複数の資料は例示形式に従います。例 PMID:1234;doi:10.1186/s12911-025-02910-2。
- **Comments**：根拠や判断の説明を入力します。改行したコメントは表示でも保持されます。
- **入力パネルの表示操作**：入力領域を閉じる、縮小・拡大する、幅を調整する操作を使います。閉じる操作を保存と誤認しないでください。
- **Submit と確認画面**：Submit は確認画面を開く段階です。表示内容を確認して確定ボタンを押すとサーバーへ登録します。Cancel は確認を中断し入力へ戻ります。

参照：`static/js/panelsearch_nanbyo/jquery.review.js`, `app.py`, `utils/api_psn.py`

### 11. Gene STR Region の入力欄

エンティティのタイプにより必要な識別情報が異なります。座標やリピートの欄では、参照ゲノムと開始・終了を取り違えないよう入力します。以下は現在の動的フォームの項目に基づく説明です。

- **Gene**：Gene Symbol、Phenotype、Rating、遺伝形式、論文、コメントを扱います。Submit 時に Gene と Phenotype を検査します。
- **STR**：Gene Symbol と Entity Name が必要です。染色体、GRCh37 / GRCh38 の Start / End、STR Repeated Sequence、STR Normal Repeats、STR Pathogenic Repeats を扱います。
- **Region**：Entity Name が必要です。染色体、GRCh37 / GRCh38 の Start / End、Region Triplosensitivity Score、Region Required Overlap Percentage、Region Variant Type、Region Verbose Name を扱います。
- **Position Chromosome**：染色体を入力する欄です。
- **Position GRCh37 / GRCh38 Start / End**：各参照ゲノムの開始・終了座標です。片方のビルドの値をもう片方に流用しないでください。
- **STR Repeated Sequence**：繰り返し配列を記録します。
- **STR Normal Repeats / Pathogenic Repeats**：正常域・病的域に関するリピート数の情報を記録します。
- **Region Haploinsufficiency Score**：スコア項目自体は定義されていますが、現在の動的フォームでは STR の表示項目に含まれます。項目名とタイプの対応を確認してから使用します。
- **Region Triplosensitivity Score**：Region のスコアを記録する欄です。
- **Region Required Overlap Percentage**：Region の必要重複率を記録します。
- **Region Variant Type / Verbose Name**：領域の変化の種類と説明用名称を記録します。

参照：`static/js/panelsearch_nanbyo/jquery.review.js`, `utils/api_psn.py`, `templates/panelsearch_nanbyo_panel_input_modal.html`

### 12. エンティティ詳細

パネルとエンティティの組合せに対する Definition、個別レビュー、コメント、変更履歴を確認します。Gene 型では More Info と Panels with this gene を使って追加情報を確認できます。

- **名称と Rating**：エンティティ名・遺伝子の正式名称、定義に対応する評価などを確認します。
- **More Info**：遺伝子の補足情報をポップアップで読みます。NCBI Gene などの参照リンク、同義語、概要、遺伝子の種類、位置等を確認できます。
- **Panels with this gene**：同じ遺伝子を含むパネルを一覧表示します。参照評価・定義評価を確認し、疾患リンクから詳細へ進みます。一覧が長いときはページ送りします。
- **Definition の概要表**：Sources、Mode of Inheritance、Publications、Phenotypes、Comments を確認します。
- **Reviews**：利用者と外部参照のレビューを表示します。Rating ごとの分布、投稿者・所属、遺伝形式、疾患、資料、コメントを読みます。
- **Created / Last Modified / Panel Version**：作成者・変更者、時刻、関係する版を確認します。作成時刻と最終変更時刻は別です。
- **History**：Review や Definition の追加・変更などを時系列で確認します。外部由来の根拠も表示されます。
- **Add Review と各操作**：担当権限と所有者に応じて、Review の追加・編集・削除や Comment の操作が表示されます。
- **Edit / Save / Cancel / Delete**：Curator または Admin の Definition 編集操作です。次章で説明します。

参照：`templates/panelsearch_nanbyo_panel_entity_detail.html`, `static/js/panelsearch_nanbyo/vgp_panel_entity_detail.js`, `static/js/panelsearch_nanbyo/vgp_user_panel_entity.js`

### 13. レビューとコメントの管理

Review の評価・疾患・資料の編集と、Review に付く Comment の編集は別の操作です。Review の元の作成者は、他の管理者が修正しても維持されます。

- **Review の Edit**：本人の Review、または対象パネルの Curator / Admin が管理できる Review を開いて変更します。入力・確認・確定の流れは Add Review と同様です。
- **Review の Delete**：対象 Review の削除確認を開きます。内容を確認して確定します。Delete の取消と確定を区別してください。
- **Add Comment**：ログイン済み利用者が Review に対する意見を追加します。空のコメントは登録しません。保存確認で確定すると反映されます。
- **Comment の Edit**：本人の Comment、または対象パネルの Curator / Admin が管理できる Comment を編集して保存します。
- **Comment の Delete**：該当 Comment の削除を確認して確定します。Review 全体の削除とは異なります。
- **他者の投稿**：Reviewer には他者の Review / Comment の編集・削除操作を原則表示しません。Add Comment は別の条件で表示されます。
- **履歴の保持**：更新・削除では新しい記録や無効化状態が作られ、活動記録や過去の履歴を参照できる構成です。画面から消えることと監査履歴が消えることは同一ではありません。

参照：`static/js/panelsearch_nanbyo/jquery.review.js`, `static/js/panelsearch_nanbyo/vgp_user_panel_entity.js`, `utils/api_psn.py`

### 14. Entity Definition の追加 変更 削除

Entity Definition は担当者が管理するパネルとエンティティの定義です。個々の Reviewer の意見とは分けて管理され、Curator Rating や概要表示、関連する版・活動記録に影響します。

- **Edit**：概要から定義編集へ切り替えます。Rating、遺伝形式、Publications、Comments 等を編集します。
- **Phenotypes**：対象疾患は現在の定義編集 UI では静的な候補として表示されます。自由な症状入力欄と誤認しないでください。
- **Save**：追加または変更の確認画面を開きます。そこで確定すると保存されます。
- **Cancel**：定義編集モードを終了して概要に戻ります。保存前の中止操作です。
- **Delete**：現在有効な Definition があるときに表示されます。削除確認を開き、確定すると現在の定義を削除扱いにします。
- **定義がない場合**：初期値を確認して必要な定義を作成します。既存定義がないときに削除ボタンが表示されないのは正常です。
- **保存後の確認**：エンティティ概要、Curator Rating、History、Version comments、活動記録に反映を確認します。

参照：`static/js/panelsearch_nanbyo/jquery.review.js`, `utils/api_psn.py`, `app.py`

### 15. TSV ダウンロードの読み方

全パネルの配布ファイル、一覧カードの個別ダウンロード、パネル詳細の Download は別の出力経路です。用途と対象範囲を確認して使用してください。

- **All panels**：/static/data/panelsearch_nanbyo/all_panel.tsv を取得する一括配布経路です。
- **一覧カードの download**：パネルごとに根拠等を取得して TSV を組み立てる経路です。
- **詳細の Download**：読み込まれた Definitive、外部参照評価、User review 等から TSV を作ります。ファイル名はパネル名.tsv です。
- **識別と疾患の列**：panel_disease_id、panel_disease_name、reference_nando_id、disease_name_en、disease_name_ja。
- **遺伝子と評価の列**：ncbi_gene_id、gene_symbol、classification。
- **根拠と遺伝形式の列**：source、source_url、moi_en、moi_ja。User review では対応するエンティティ詳細 URL が入ります。
- **重複する遺伝子**：根拠や Review ごとに行が作られるため、同じ遺伝子が複数行に現れます。行数を遺伝子の種類数と見なさないでください。
- **表示フィルターとの関係**：詳細の Download は取得済みデータから作るため、Filter entities の表示結果だけをそのまま抽出する用途には向きません。

参照：`static/js/panelsearch_nanbyo/jquery.vgp.js`, `static/js/panelsearch_nanbyo/vgp_panel_detail.js`

### 16. Ontology 管理

DB に登録された Ontology を閲覧する機能と、ローカルの TTL を読み込んで構造を分析する機能があります。ファイルをブラウザーで分析する段階と、サーバーに確定アップロードする段階は別です。

- **Ontology In DB**：ID、TTL File、検査用パネル数、未指定疾患群数、Description、Valid、Created At を一覧表示します。
- **行の選択と Load Selected Ontology From DB**：対象行を選び、登録済み Ontology を読み込みます。旧版を読み込む操作は、使用中の版へ切り替える操作ではありません。
- **Ontology From File**：TTL ファイルを選択、または対応するドラッグ＆ドロップで読み込みます。拡張子選択は .ttl、.txt、.rdf、.owl を許可しますが、解析は Turtle 形式です。
- **進行状況と統計**：読み込み・分析の状態、有効クラス、obsolete、未使用ノードなどの数を確認します。
- **ツリービュー**：検査用パネルと未指定疾患群の階層を展開して確認します。
- **使用中ノード一覧**：対象の分類に使用されるノードを ID、Type、日本語・英語ラベルで確認します。
- **Obsolete ノード一覧**：廃止されたノードを確認します。
- **未使用ノード一覧**：使用中の分類に入らないノードを確認します。ファイル内の全クラス数と利用対象ノード数は異なります。
- **現在使用中 Ontology と比較**：ファイル側の分析結果を現在使用中の Ontology と比較し、追加・削除等を確認します。各パネル見出しで展開・折りたたみします。
- **MD5**：読み込んだファイルを識別するためのハッシュです。版の名前・説明と併せて確認します。
- **アップロード確認**：ファイル名、MD5、指定・未指定パネル数、追加・削除ノード数、Comment を確認します。Comment は空欄にできません。
- **Upload の確定**：Admin が確定するとサーバーで再分析し、使用中の Ontology、パネル、階層、版との関連を更新します。完了後にページが再読み込みされます。

参照：`templates/panelsearch_nanbyo_ontology.html`, `static/js/panelsearch_nanbyo/ontology.js`, `static/js/panelsearch_nanbyo/ontology_analysis.js`, `static/js/panelsearch_nanbyo/jquery.ontology_treeview.js`, `utils/api_psn_ontology.py`

### 17. 管理画面の共通操作

管理画面の左サイドバーから各ページへ移動します。権限に応じてメニューが変わります。一般利用者でもプロフィールや自分のレビューなどを利用します。

- **サイドバー**：ユーザー、グループ、グループ活動、アクティビティ、担当活動、認証ログ、メール、プロフィール、レビューへの導線です。折りたたみ操作で表示幅を調整できます。
- **検索欄**：指定された列の文字列で絞り込みます。入力を消して解除します。何の名前・メールを検索する欄か各章を確認します。
- **並べ替え**：矢印のある見出しで昇順・降順を切り替えます。
- **Per page とページ送り**：多くの管理一覧では 10、30、50、100、200 件から表示件数を選べます。ページ番号、表示範囲、合計を確認します。
- **チェックボックス**：行選択と全選択です。表示範囲の選択が操作対象になります。チェックだけでは保存や削除を実行しません。
- **サイドパネルと詳細**：ユーザー・活動の行を開くと詳細や履歴が表示されます。閉じるボタンで一覧へ戻ります。
- **確認ダイアログ**：確定で送信、キャンセルで中止します。表示された対象と操作種別を確認します。

参照：`templates/panelsearch_nanbyo_admin_layout.html`, `static/js/panelsearch_nanbyo/admin.js`

### 18. ユーザー管理

アカウントの状態、プロフィール、グループ内の役割を管理します。氏名から開く詳細編集と、一覧の状態変更アクションを区別して使用します。

- **一覧**：氏名、メール、所属機関・部署、グループ、ステータス、登録日を確認します。
- **名前 / メールアドレス**：利用者を文字で絞り込みます。
- **グループ**：グループ候補を選択して一覧を絞り込みます。候補の Filter でグループ名を探せます。
- **ステータス**：承認、申請、無効、停止、拒否、退会の区分で絞り込みます。申請には認証前後など複数の内部状態が含まれます。
- **グループの表示と詳細**：グループタグや追加表示を開き、所属グループと Reviewer / Curator を確認します。役割変更を行うとグループ活動記録に反映されます。
- **承認 / 拒否**：メール認証済み申請など、現在の状態に応じた操作を確認・確定します。
- **認証メール再発送**：認証期限満了の状態などで表示される再認証の操作です。実際にメール送信へつながります。
- **アカウントを停止 / 再開**：承認済み利用者の停止、停止済み利用者の再開を行います。
- **ユーザー削除**：一覧の削除または詳細の削除を使用します。実装の確認画面では取消不能の注意が表示され、詳細側ではメールの再入力を検査します。
- **氏名クリックと詳細編集**：Account、氏名の日本語・英語、所属機関・部署、職名、メール等を確認し、Edit → Save または Cancel を操作します。
- **Admin の切替**：詳細編集に管理者種別の切替があるため、グループ内の Curator 変更と混同しないでください。Admin は全体の管理権限に関わります。
- **一覧へ戻る**：詳細の戻るアイコンで利用者一覧に復帰します。

参照：`templates/panelsearch_nanbyo_admin_user.html`, `static/js/panelsearch_nanbyo/admin_user.js`, `app.py`, `utils/api_google_auth.py`

### 19. グループ管理

グループとメンバー、担当疾患パネルを設定します。Admin は全グループを管理し、Curator は担当グループのメンバー管理を行います。担当パネルを関連付けることで、そのグループの利用者に対応するパネルの役割が適用されます。

- **グループ一覧**：名前で絞り込み、グループを選択します。Admin と Curator では表示範囲が異なります。
- **グループ追加**：Admin がグループ名を入力し作成します。
- **名称編集 / グループ削除**：Admin の操作です。削除は有効フラグを変更する構成で、無効なグループからの権限は適用されません。
- **メンバータブ 左一覧**：グループ外の利用者を検索します。氏名、メール、所属の検索に対応します。
- **メンバータブ 右一覧**：所属メンバーと役割を確認します。こちらも氏名・メール・所属で絞り込みます。
- **右向き矢印**：左一覧の対象者を選択し、グループへ追加します。
- **左向き矢印**：右一覧の対象者を選択し、グループから外します。
- **Reviewer / Curator**：メンバーの役割を切り替えます。Admin またはそのグループの Curator に許可される操作です。
- **招待**：未登録の利用者を検索した場合、招待導線が表示されます。宛先、グループ名、件名、本文を確認するメール送信操作です。
- **グループの疾患登録**：グループに登録された担当パネルと告示番号を一覧表示します。
- **担当疾患の追加 / 削除**：Admin が候補検索からパネルを選び、追加するを押す、または行の削除を行います。Curator は担当疾患関連の変更を行いません。
- **変更記録**：メンバー追加・削除・役割変更は Group Activity の対象です。グループ自体や担当パネルの追加・削除は現在の Group Activity に記録されません。

参照：`templates/panelsearch_nanbyo_admin_group.html`, `static/js/panelsearch_nanbyo/admin_group.js`, `static/js/panelsearch_nanbyo/admin_group_admin.js`, `utils/api_psn.py`, `app.py`

### 20. グループ活動

グループのメンバー追加、削除、役割の変更を監査する一覧です。対象ユーザーと実際に操作した変更者を分けて読みます。

- **一覧の列**：ユーザー、グループ名、役割、変更履歴、変更者を確認します。
- **名前 / メールアドレス**：変更対象となったユーザーの氏名・メールを検索します。変更者名の検索とは異なります。
- **変更履歴**：追加、削除、Reviewer → Curator、Curator → Reviewer などを確認します。
- **変更者**：誰が操作したかを確認します。対象ユーザーと同じとは限りません。
- **並べ替えとページ送り**：列見出しと Per page を利用して目的の記録へ移動します。
- **記録の範囲**：グループ作成・削除やパネル関連付けの全操作を網羅する一覧ではありません。

参照：`templates/panelsearch_nanbyo_admin_group_activity.html`, `static/js/panelsearch_nanbyo/admin_group_activity.js`, `utils/api_psn.py`

### 21. アクティビティ

Review、Comment、Definition の変更を、パネル、版、エンティティ、期間で探します。行を開くと変更前後の値を確認できます。

- **パネルフィルター**：ツリーから対象パネルを選びます。選択を解除する操作で範囲を戻します。
- **パネル版フィルター**：対象パネルの版から活動を絞り込みます。パネル選択により候補が読み込まれます。
- **エンティティフィルター**：候補を文字で絞り込み、チェックして対象を選びます。
- **From / To**：期間を選択します。変更するとサーバーから活動一覧を読み直します。
- **活動一覧**：パネル、エンティティ、利用者、操作種別、時刻等を確認します。
- **行の展開**：変更前と変更後の Rating、疾患、遺伝形式、資料、コメント等を表示します。
- **パネル・エンティティリンク**：対象の詳細画面へ移動します。
- **操作の区分**：Review の add / change / delete、Definition の操作などを読みます。Comment の追加・変更・削除は Review の change として記録される構成です。
- **並べ替え / ページ送り**：一覧の列、表示件数、ページを変更して記録を探します。

参照：`templates/panelsearch_nanbyo_admin_activity.html`, `static/js/panelsearch_nanbyo/admin_activity.js`, `utils/api_psn.py`, `app.py`

### 22. 担当アクティビティの確認

Curator が担当パネルの最新活動を確認し、確認済み・未読を切り替える画面です。Admin は全体の活動を扱います。一般の全活動一覧と異なり、Review / Definition ごとの最新活動を中心に提示します。

- **担当活動一覧**：担当範囲のパネル、エンティティ、利用者、操作、時刻を確認します。
- **行のクリック**：右サイドパネルにパネル、エンティティ、利用者、活動履歴を表示します。
- **Curate**：対象エンティティの Definition 編集につながる詳細ページを開きます。
- **確認処理**：対象活動を確認済みにします。行や履歴の表示に確認状態を反映します。Review の評価を承認・確定するボタンとは別です。
- **未読に変更**：確認を取り消して未確認状態へ戻します。
- **履歴表示**：同じ Review または Definition に関する活動履歴を確認します。
- **閉じる**：右パネルを閉じ、一覧へ戻ります。
- **Per page / ソート**：表示件数と並び順を変更して担当記録を探します。

参照：`templates/panelsearch_nanbyo_admin_incharge.html`, `static/js/panelsearch_nanbyo/admin_incharge.js`, `utils/api_psn.py`

### 23. 認証ログ

ログインなどの認証イベントを、対象ユーザー、期間、成功・失敗で確認します。失敗の理由と時刻を併せて読むと認証状態の調査に役立ちます。

- **名前 / メールアドレス**：認証ログのユーザー名・メールを部分一致等で絞り込みます。
- **From / To**：期間を設定し、対象の記録を読み込みます。
- **結果**：成功・失敗のチェックで絞り込みます。
- **Date / ユーザー名**：イベント時刻と対象利用者を確認します。
- **user-Agent**：利用環境の情報を確認します。
- **動作 / 結果 / Reason**：認証の種類、成功・失敗、理由を確認します。
- **並べ替え / 件数 / ページ**：見出し、Per page、ページ番号を使って記録を探します。
- **0 件の場合**：名前、期間、結果の条件を解除してから再確認します。

参照：`templates/panelsearch_nanbyo_admin_authentication.html`, `static/js/panelsearch_nanbyo/admin_authentication.js`, `utils/api_google_auth.py`

### 24. プロフィール

自分の登録情報を確認・編集します。管理者が他者を編集するユーザー管理とは異なり、この画面はログイン中の本人のプロフィールを扱います。

- **登録情報**：Account、氏名の日本語・英語、所属機関・部署、職名、メール等を確認します。
- **Edit**：編集欄を表示します。
- **Save**：必須欄とメール形式を検査し、保存します。成功後はページを再読込します。
- **Cancel**：編集を中止して閲覧表示へ戻します。
- **Delete**：退会・アカウント削除の確認を開きます。元のメールと入力した確認メールが一致する必要があります。
- **メールが不一致**：エラーメッセージが表示され、削除確定へ進みません。
- **削除後**：成功すると対応するサービスのログアウトへ進みます。

参照：`templates/panelsearch_nanbyo_admin_profile.html`, `static/js/panelsearch_nanbyo/admin_profile.js`, `app.py`

### 25. 自分のレビュー

自分が投稿した Review と関連する自分の Comment を、パネル・エンティティごとに確認する画面です。パネル名、エンティティ名、更新日時の順で整理して表示する構成です。

- **パネル名・エンティティ名**：対応する詳細へのリンクを開きます。
- **評価**：自分の Review の Rating を確認します。
- **Mode of inheritance / Phenotype**：選択した遺伝形式と疾患を読みます。
- **Publications**：登録した PMID / DOI などの根拠リンクを開きます。
- **Comment**：関連コメント、作成・最終変更の日時、関連する版を確認します。
- **Created / Last Modified / Panel Version**：Review の時刻と版を確認します。コメント自身にも対応する時刻情報があります。
- **編集したい場合**：エンティティ名のリンクから詳細へ進み、権限のある Review / Comment の Edit を使用します。この画面自体は一覧・参照が中心です。
- **レビューがない場合**：一覧が空になることがあります。登録に失敗したと決めつけず、対象のアカウントと投稿先を確認します。

参照：`templates/panelsearch_nanbyo_admin_review.html`, `static/js/panelsearch_nanbyo/admin_review.js`, `app.py`

### 26. メール設定

メールの送信履歴、テンプレート、SMTP 設定を確認する Admin 用画面です。Mail Log と Mail Template は操作機能があり、Mail SMTP Setting は現在の実装では閲覧専用です。

- **Mail Log**：受信者の名前・メール、From / To の日付、Type、Status で検索条件を指定します。
- **Status**：Pending、Sent、Failed の状態を選択します。
- **Load**：条件に合う送信履歴を読み込みます。ログの検索・ページ送りも利用します。
- **メール一覧**：種類、受信者、所属、メール、送信時刻、ステータスを確認します。
- **行の詳細**：件名、From、To、送信時刻、状態、本文、エラーを確認するモーダルを開きます。
- **Resend**：対象のログで表示される再送操作です。実際の送信を発生させるため、宛先と既送信状況を確認して確定します。
- **Close**：詳細モーダルを閉じます。
- **Mail Template**：対象の template を選び、Subject と body を確認します。
- **Modify / Save / Cancel**：Modify で件名・本文の編集を開始し、Save の確認で確定します。件名・本文は空欄にできません。Cancel で選択テンプレートの保存済み内容へ戻します。
- **テンプレート変数**：{user_name}、{group_title}、{GOOGLE_FORM_URL} 等、選択したテンプレート内の差し込み用文字列を確認して保持します。
- **Mail SMTP Setting**：SMTP Server、Port、SSL 465 / TLS 587、User Name、APP Password、From Name、From Email を確認します。
- **SMTP の編集可否**：入力欄は無効化され、変更・保存・取消のボタン群はコメントアウトされています。この画面から SMTP を変更する手順はありません。

参照：`templates/panelsearch_nanbyo_admin_mail.html`, `static/js/panelsearch_nanbyo/admin_mail.js`, `app.py`

### 27. エラーとよくある状況

表示されない機能や読み込み失敗は、権限、入力、選択範囲、セッション、データの有無を順に確認します。HTTP の成功応答でも JSON 内に error がある場合があります。

- **Add Review がない**：Nanbyo にログインしているか、対象パネルに関連する有効グループで Reviewer / Curator を担当しているかを確認します。
- **Edit / Delete がない**：投稿の所有者と対象パネルの担当役割を確認します。Definition の Delete は現在有効な定義がある場合だけ表示されます。
- **管理ページからログインへ戻る**：対応する Nanbyo セッションが失効している可能性があります。通常のログインをやり直します。
- **not enough privilege**：開いたページ・操作に必要な Admin / Curator などの権限を確認します。
- **検索が 0 件**：検索語、Panel / Gene、Tree の選択範囲、日付、グループ、ステータスなどの条件を解除して再確認します。
- **Show(0) が開かない**：対応データが 0 件の場合の正常な表示です。
- **Loading が終わらない**：ネットワーク接続と API の応答を確認し、しばらく待ってから再読込します。複数の外部データ取得に依存する画面があります。
- **Please input gene / phenotype / entity name**：文字入力だけでなく候補選択と必須フィールドを確認します。
- **Review has changed / HTTP 409**：他の操作で最新記録が変わった可能性があります。再読込し、最新 Review と編集内容を照合します。
- **Ontology の解析エラー**：Turtle 形式、必要な NANDO 構造、循環する親子関係などを確認します。
- **Mail Failed**：詳細でエラーを確認し、SMTP と宛先を調べます。すぐに何度も Resend しないようにします。
- **URL を直接開くと一覧へ戻る**：パネル ID やエンティティ識別情報が不足している可能性があります。一覧・詳細の実際のリンクから移動します。

参照：`app.py`, `static/js/panelsearch_nanbyo/jquery.review.js`, `static/js/panelsearch_nanbyo/ontology_analysis.js`, `utils/api_psn.py`

### 28. 補助テンプレートと未実装の画面

リポジトリに存在する HTML ファイルが、すべて独立したページとして公開されるわけではありません。ページルートに接続された 13 画面と、共通・部分・未実装のテンプレートを区別します。

- **panelsearch_base**：公開ページの共通ヘッダー、スタイル、スクリプト等の土台です。独立ページではありません。
- **admin_layout**：管理画面のサイドバーと共通レイアウトです。独立ページではありません。
- **panel_input_modal**：レビュー入力に関連する部分テンプレートです。現在の動的レビュー UI との項目差に注意します。
- **panelsearch_error**：権限エラーなどのメッセージと戻り先を表示する共通画面です。
- **admin_statistics**：テンプレートには not yet があり、対応する Nanbyo ページルートがありません。統計グラフの利用手順はありません。
- **admin の別名**：/panelsearch_nanbyo_admin と /panellist_nanbyo_admin はユーザー管理への別ルートです。独立した機能として重複カウントしません。

参照：`templates/panelsearch_nanbyo_admin_statistics.html`, `templates/panelsearch_nanbyo_admin_layout.html`, `templates/panelsearch_error.html`, `app.py`

