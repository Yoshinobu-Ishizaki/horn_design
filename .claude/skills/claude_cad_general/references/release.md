# 成果物(STEP/STL)の配布と git 管理(release)

build123d で作った STEP/STL を、環境を作れない人にも最終稿としてすぐ渡しつつ、リポジトリ履歴を太らせないための運用。共通仕様 16 の詳細。

## 1. 方針

| 項目 | 方針 |
|---|---|
| 正(source of truth) | build123d の Python スクリプト。STEP/STL は派生物 |
| 既定(モード A) | GitLab Release に成果物を添付する。リポジトリ本体には STEP/STL をコミットしない |
| 代替(モード B。ユーザーが希望したときだけ) | タグごとに、リポジトリの `release/<タグ>/` へコミットする |
| 途中生成物 | `.gitignore` で管理外(`output/` ほか) |
| 配布の単位 | タグ(バージョン)単位。生成のたびにコミットや Release を作らない |

ユーザーが明示的に希望しない限り、モード A で進める。

### 根拠

- STEP はテキストだが、CAD カーネルの出力ごとに順序や ID が変わり、差分がほぼ読めない。STL は大きく圧縮も効きにくい。通常の git に入れ続けると履歴が肥大化し、一度入ると消しにくい。
- Release 添付ならリポジトリ容量を使わず、LFS の導入(利用者が `git lfs install` を忘れるとポインタファイルだけが落ちる事故)も要らない。
- 利用者は Release ページからダウンロードするだけで済む。
- モード B は、Release 機能が使えない・権限がない・`git clone` だけで完結させたい場合の逃げ道。

## 2. 事前確認(最初にする)

1. 対象リポジトリの GitLab URL とプロジェクト ID(`git remote -v`、API)。
2. 配布モード(A / B)。ユーザーが何も言わなければ A を提案して進める。
3. タグ名(例: `v1.0.0`、または日付ベース)。`git tag -l` で既存タグと重複しないか確かめる。
4. 作業ツリーがきれいか(`git status`)。未コミットの変更があるまま成果物を作らない。
5. 認証手段(`glab auth status`、または環境変数のトークン)。トークンはチャットに貼らせない・出力しない。
6. 自分のロールが Release を作れるか(通常 Developer 以上。社内 GitLab の設定で要確認)。
7. STL を配布対象に含めるか(含めるなら合計サイズの見積もり)。

## 3. 生成と検証(共通)

1. タグを打つ対象のコミットのスクリプトで STEP(必要なら STL)を生成し、`output/` などの一時ディレクトリに出す(git 管理外)。
2. 生成後に簡易検証する。
   - ファイルが空でない。期待する点数が揃っている。
   - STEP が再読込できる(`import_step` など)。
   - 可能なら体積やバウンディングボックスを前回タグと比べ、異常を検知する。
3. `manifest.json` を作り、成果物と一緒に配布する(`scripts/make_manifest.py`)。記載項目:
   - ソースのコミット SHA、タグ名
   - build123d / OCP / Python のバージョン
   - 生成日時
   - 各ファイルのファイル名・サイズ・SHA256
4. 点数が多い場合(200 点規模)は、個別ファイルに加えて一括 ZIP(`<repo>-<tag>-step.zip`)も作る。STL は別 ZIP(`<repo>-<tag>-stl.zip`)に分けると、STEP だけ欲しい人が軽く落とせる。

```
uv run python <このスキル>/scripts/make_manifest.py --tag v1.0.0 --out output/manifest.json output/step output/stl
```

検証や生成に失敗したら、Release の作成へ進まず、原因を報告する。

## 4. モード A(既定): GitLab Release に添付

1. タグを作って push する(実行前にユーザーの確認を取る)。
   ```
   git tag -a v1.0.0 -m "release v1.0.0"
   git push origin v1.0.0
   ```
   日本語のタグメッセージは、Write で書いた UTF-8 ファイルを `git tag -a v1.0.0 -F <ファイル>` で渡す。
2. 成果物をアップロードして Release を作る(実行前にユーザーの確認を取る)。どちらかを環境に合わせて選ぶ。

   **方法 1: glab CLI(簡単)**
   ```
   glab release create v1.0.0 --notes-file RELEASE_NOTES.md ./output/<repo>-v1.0.0-step.zip ./output/manifest.json
   ```
   glab のバージョンによりアセット添付の挙動(Generic Package 経由か等)が違う。実行前に `glab release create --help` で確かめる。

   **方法 2: Generic Package Registry + Release API(確実)**
   ```
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" --upload-file output/<repo>-v1.0.0-step.zip "$GITLAB_URL/api/v4/projects/$PROJECT_ID/packages/generic/<package名>/v1.0.0/<repo>-v1.0.0-step.zip"
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" --header "Content-Type: application/json" --data @release.json "$GITLAB_URL/api/v4/projects/$PROJECT_ID/releases"
   ```
   `release.json` には `tag_name`、`description`、`assets.links[]`(`name` / `url` / `link_type: "package"`)を入れる。
3. 作成後、Release ページを開く(または API で取得する)などして、リンクが生きていて、ファイルが落とせることを確かめる。
4. ユーザーに Release の URL を報告する。README に「最新の成果物は Releases から」となければ、追記を提案する。

CI/Runner が使えるなら、タグ push を契機に生成から添付までを CI で自動化できる。初版では対象外。希望があれば提案する。

## 5. モード B(ユーザーが希望したとき): タグごとに `release/` へ

```
release/
  v1.0.0/
    step/*.step
    manifest.json
  v1.1.0/
    ...
```

- 原則 STEP のみコミットする。STL は「LFS に入れる」「入れない(必要なときに STEP から再生成)」をユーザーに確認する。
- STL を LFS に入れる場合のみ、`.gitattributes` に `release/**/*.stl filter=lfs diff=lfs merge=lfs -text` を設定する。サーバー側で LFS が有効か、利用者が `git lfs install` 済みかを事前に確かめる(未済だとポインタファイルが落ちる)。

手順(順序が重要):

1. `release/<タグ>/` に成果物と manifest を置く。
2. `git add release/<タグ>`(ファイルを指定して追加)してコミットする(例: `release: v1.0.0 artifacts`)。
3. 成果物を含むそのコミットにタグを打つ(タグを先に打たない)。manifest のソース SHA は「スクリプトの最終コミット」を指し、成果物コミット自身ではない。
4. push(コミットとタグ)。実行前にユーザーの確認を取る。
5. 過去タグの `release/` は削除・上書きしない(履歴の再現性のため)。

注意:

- 毎回、数十から数百 MB が積み上がる。実行前に今回の合計サイズを表示し、肥大の見込みを伝える。合計 100 MB を超えるときは、モード A への切り替えを提案する。
- 一度コミットしたバイナリは履歴から消しにくい。コミット前に必ず最終確認を取る。

## 6. `.gitignore` の推奨

```
output/
dist/
build/
*.step
*.stp
*.stl
!release/**/*.step
!release/**/*.stl
```

モード A だけの運用なら `!release/...` の 2 行は要らない。

## 7. 安全・確認ルール

- 次は必ず、実行前にユーザーの明示的な確認を取る: タグの作成と push、Release の作成、`release/` へのコミットと push。
- トークンなどの認証情報は、チャットに出さない・ファイルに書かない・コミットしない。
- 既存のタグ・Release・過去の `release/<タグ>/` を上書き・削除しない。必要なら別のタグを提案する。
- 生成や検証に失敗したら、Release の作成へ進まず、原因を報告する。

## 8. 未決事項(案件ごとに確認)

1. 社内 GitLab のバージョンと、glab のアセット添付の挙動(方法 1 / 2 のどちらを標準にするか)。
2. Release の作成権限と、Generic Package Registry の有効化状況・容量制限。
3. STL を配布対象に含めるか。
4. タグの命名規約(セマンティックバージョンか日付か)。
5. CI 自動化を将来やるか。
