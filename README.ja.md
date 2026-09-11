# auto-karaoke

[中文](README.md) · [English](README.en.md) · **日本語**

日本語のカラオケ動画を作成するツールです。音源分離、歌詞のタイミング調整、漢字のふりがな、単語・モーラ単位の色変化、歌手別の色分けに対応し、伴奏と分離ボーカルを別々の音声トラックに収録した MP4 を出力します。

## サンプル

漢字のふりがな、上下交互の歌詞表示、歌手名と色分け：

![ふりがなと歌手別の色分けを表示したカラオケ字幕](docs/images/sample-japanese.jpg)

<details>
<summary>タイトル画面と英語歌詞の表示</summary>

![冒頭のタイトル画面](docs/images/sample-title.jpg)

![元の映像に重ねた英語のカラオケ字幕](docs/images/sample-english.jpg)

</details>

[サンプルの出典](docs/images/README.md)

| Skill | 用途 |
| --- | --- |
| `karaoke-setup` | 環境を確認し、ユーザーの承認を得て依存関係をインストール・修復 |
| `audio-separate` | 音声・動画から伴奏とボーカルを分離 |
| `karaoke-author` | 歌詞の読みとタイミングを作成・校正 |
| `karaoke-render` | 字幕データと分離音源から動画を生成 |

プレーヤーは別プロジェクトで開発しています：[auto-karaoke-player](https://github.com/frip-fans/auto-karaoke-player)。

## インストール

Claude Code を使う場合は、[プラグインのインストール手順](plugins/auto-karaoke/README.md#claude-code)を参照してください。また、[CLI の手動インストール手順](docs/manual-install.md)（中国語）から、ターミナルで直接利用できます。

Codex が動作するパソコン、空きディスク容量、初回インストール時のインターネット接続が必要です。制作には Python 3.11 以降と FFmpeg、字幕の描画には日本語フォントを使用します。音源分離と歌詞の音声アライメントには NVIDIA GPU を推奨します。CPU でも実行できますが、処理に時間がかかります。選択したモデルを実行できるかどうかは、プラグインがハードウェアと必要なバックエンドを確認します。

このリポジトリのルートディレクトリで実行してください。Python 環境を先に手動設定する必要はありません。

```bash
codex plugin marketplace add .
codex plugin add auto-karaoke@frip-fans
```

新しい Codex セッションを開き、次のように依頼します。

```text
$karaoke-setup このパソコンを確認して、音源分離に必要なインストール項目を教えてください。
```

Codex はまず環境を変更せずに確認できます。依存関係のインストール、環境の作成、モデルのダウンロードが必要な場合は、内容と保存先を提示し、ユーザーの明確な承認を得てから実行します。各制作 skill も同じルールに従います。

## 使い方

```text
$audio-separate この MV を MDX23C で伴奏とボーカルに分離してください。
$karaoke-author 歌詞と分離音源からタイムラインを作成し、確認が必要な箇所を挙げてください。
$karaoke-render 確認済みのタイムラインと background.png から 1080p 動画を作成してください。
```

`auto-karaoke` CLI を直接使うこともできます。[コマンドと字幕設定](docs/production.md)（中国語）を参照してください。歌詞と読みは人による校正が必要です。現在、音声アライメントのコマンドで処理できる長さは 1 回につき最大 60 秒です。

2 音声トラックで出力するには、`dual_audio: true` と `dual_audio_source: "vocals"` を設定します。第 1 トラックが伴奏の `Instrumental`、第 2 トラックが分離ボーカルの `Vocals` です。

[プラグインのインストール手順](plugins/auto-karaoke/README.md)（中国語） · [歌詞アノテーションツール](tools/lyric-annotator.html)

## ライセンス

[GPLv3](LICENSE)（`GPL-3.0-only`）。第三者の依存ライブラリとモデルの重みには、それぞれのライセンスが適用されます。サンプル画像に含まれる第三者のアートワークと歌詞は、本プロジェクトのコードライセンスの対象外です。
