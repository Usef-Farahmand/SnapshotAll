# Code signing policy

## Current status

**Windows builds are not code-signed yet.** When you run the installer or the portable `.exe` for the first time, Windows Defender SmartScreen may show *"Windows protected your PC"* / *"Unknown publisher"*.
This does not mean the file is infected — it means Windows has never seen this exact file or publisher before.

> Maintainers: update this section when signing is enabled (see [Enabling signing](#enabling-signing-for-maintainers)).

## For users

**To run the app anyway:** click **More info → Run anyway**.

**To check that the download is genuine:**

1. Download the file only from the [official Releases page](https://github.com/Usef-Farahmand/SnapshotAll/releases).
2. Every release includes `SHA256SUMS.txt`. Compare it with your file in PowerShell:
   ```powershell
   Get-FileHash .\SnapshotAll_Setup.exe -Algorithm SHA256
   ```
3. Optional: right-click the downloaded file → **Properties** → tick **Unblock** → OK.

The full source code is public and every release is built from it by GitHub Actions ([workflow](.github/workflows/build.yml)).

## Why does SmartScreen warn?

SmartScreen judges downloads by **reputation**:

- An **unsigned** file is judged by its own hash. Every new release is a new file, so the warning comes back with each release until enough people have run it.
- A **signed** file also carries the reputation of its signing certificate, which persists across releases. A brand-new certificate can still warn at first.
- Since 2024, Microsoft treats **EV** and **OV** certificates the same: EV no longer gives instant reputation, so a paid EV certificate is not worth the extra cost just for SmartScreen.

## Options to remove the warning

| Option | Cost | Notes |
|---|---|---|
| **SignPath Foundation** (free for open source) | Free | Needs a public repo, an OSI license (MIT ✔), CI-built releases, MFA on GitHub, a published code-signing policy (this file) and a short application. The certificate is issued to *SignPath Foundation*, so that name appears as the publisher. **Best fit for this project.** |
| **OV code-signing certificate** (Sectigo, DigiCert, SSL.com, …) | Paid, yearly | Certificates must live on a hardware token or cloud HSM. Reputation still builds with downloads. |
| **Azure Artifact Signing** (formerly Trusted Signing) | Monthly fee | Availability is limited by country and developer type — check the current rules before planning around it. |
| **Microsoft Store (MSIX)** | Developer account | Store apps do not show the SmartScreen prompt, but the app must be packaged as MSIX. |

## Enabling signing (for maintainers)

### 1. Apply to SignPath Foundation

1. Make sure GitHub two-factor authentication is on for every maintainer.
2. Keep this file and the [Code of Conduct](CODE_OF_CONDUCT.md) in the repository, and link to this policy from the README (already done).
3. Apply at <https://signpath.org> ("Apply for free code signing"). Releases must already exist and be built from source in CI.
4. After approval, create the project, a signing policy and an artifact configuration in SignPath, and add these to the repository's **Settings → Secrets and variables → Actions**:
   - secret `SIGNPATH_API_TOKEN`
   - variables `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`

### 2. Add the signing step to the workflow

SignPath signs an artifact that was uploaded to GitHub first. Sketch (verify names against the current SignPath documentation):

```yaml
      - name: Upload unsigned installer
        id: upload-unsigned
        uses: actions/upload-artifact@v4
        with:
          name: SnapshotAll_Setup_unsigned
          path: Output/SnapshotAll_Setup.exe

      - name: Sign with SignPath
        uses: signpath/github-action-submit-signing-request@v1
        with:
          api-token: ${{ secrets.SIGNPATH_API_TOKEN }}
          organization-id: ${{ vars.SIGNPATH_ORGANIZATION_ID }}
          project-slug: ${{ vars.SIGNPATH_PROJECT_SLUG }}
          signing-policy-slug: ${{ vars.SIGNPATH_SIGNING_POLICY_SLUG }}
          github-artifact-id: ${{ steps.upload-unsigned.outputs.artifact-id }}
          wait-for-completion: true
          output-artifact-directory: Output
```

Place it after *Build installer* and before the checksum / release steps, so the published installer and its checksum are the signed ones.

### 3. Update the documentation

Once signing works, replace the *Current status* section above, and add this line to the README and to the download page:

> Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).

## Signing process (once enabled)

- Only artifacts built by the GitHub Actions release workflow are submitted for signing — never local builds.
- Roles: the repository owner, [Usef Farahmand](https://github.com/Usef-Farahmand), is the author, reviewer and approver.
- The private key is held by the signing service, not by the maintainer.

## Privacy

SnapshotAll connects only to the websites you ask it to capture and, if neither Microsoft Edge nor Google Chrome can be used, downloads Chromium once. It does not send any data about you or your captures anywhere.

## Reducing antivirus false positives

Apps built with PyInstaller are sometimes flagged by antivirus software. This project builds in *one-folder* mode (not single-file), does not use UPX compression, and is built only by CI. If a scanner flags a release, report it as a false positive to the vendor (for Microsoft Defender: <https://www.microsoft.com/wdsi/filesubmission>).
