# Zero-cost Alibaba Cloud trial runbook

This deployment has a **zero out-of-pocket** constraint. Trial credits and free
product quotas are the only permitted funding sources. Do not create or enable a
resource when the final Alibaba Cloud confirmation page does not show that the
selected configuration is covered by an active free trial.

## Verified trial offers

The following offers were visible in the authenticated Alibaba Cloud console on
2026-07-20. They must be re-verified immediately before each resource is created:

| Service | Trial shown in console | Deployment use |
|---|---|---|
| ECS | USD 90 credit, valid for 3 months; combined ECS and system-disk cap USD 0.25/hour | One demo host |
| Network traffic | 200 GB/month outside mainland China plus 20 GB/month in mainland China | Public demo traffic |
| OSS | 500 GB for 1 month on the individual free tier | Private replay bundles |
| Model Studio | 70+ million free model tokens | Qwen inference |

Alibaba Cloud requires a supported payment method to claim free-tier products.
Usage beyond a credit, time, traffic, storage, request, or token quota can be
billed. A payment method is therefore **not** evidence that a resource is free;
the active trial and final zero-cost coverage must be visible in the console.

## Approved demo configuration

- Region: Singapore.
- ECS: Economy Type e, 2 vCPU, 4 GiB RAM.
- Image: Ubuntu 22.04.
- System disk: 100 GiB ESSD Entry included in the selected trial profile.
- Displayed rate: USD 0.046/hour, below the USD 0.25/hour trial cap.
- Quantity: one instance.
- Networking: use the trial instance's included public connectivity; do not add a
  separately billed EIP, NAT gateway, load balancer, CDN, or paid bandwidth plan.
- HTTPS: use `latch.<public-ip-with-dashes>.sslip.io` as the free DNS name and let
  Caddy obtain a per-host certificate. Verify that the name resolves to the trial
  instance before deploying; do not purchase a domain for the demo.
- Storage: one private OSS bucket claimed through the 500 GB/one-month free-tier
  offer. Do not activate OSS from the pay-as-you-go activation screen.
- Models: use an Alibaba Cloud Model Studio API key and its free token grant. Do
  not use the Qwen Cloud pay-as-you-go API-key flow.
- Credentials: attach a least-privilege ECS RAM role for OSS and set
  `ALIBABA_CLOUD_ECS_RAM_ROLE`; do not store Alibaba account-level AccessKeys.
- Add-ons: no backup, snapshot plan, security add-on, support plan, subscription,
  auto-renewal, or marketplace image.

At USD 0.046/hour, 23 complete days cost USD 25.392 of trial credit. This leaves
more than USD 64 of the USD 90 ECS credit before allowing for any unexpected
eligible usage. This estimate is a guardrail, not a guarantee; the console's
credit balance is authoritative.

## Mandatory go/no-go checks

Before any create, enable, or confirm action:

1. Complete the Alibaba Cloud account profile and add the payment method required
   by the free-tier terms manually; never place payment details in this repo.
2. Confirm the account is eligible for the named free trial and has not used the
   one-time offer previously.
3. Confirm the exact selected resource is covered by the trial, the displayed
   hourly amount is at or below the trial cap, and the immediate charge is USD 0.
4. Confirm quantity is one and every paid add-on and auto-renewal control is off.
5. Record the trial start/end dates and remaining credit in the private operator
   checklist. Do not expose account or payment information in proof screenshots.
6. Create a billing alert at USD 1 of *actual out-of-pocket charges* if Alibaba
   supports it. The alert is secondary; it does not replace the trial checks.

Stop immediately if a screen says only "pay-as-you-go," asks for a purchase,
shows a non-zero immediate charge, omits the trial coverage, or indicates that
the account is ineligible. Do not proceed on the assumption that a later credit
will reimburse the charge.

## During the demo

- Check the ECS credit, network usage, OSS quota/expiry, and Model Studio token
  quota daily while the public demo is running.
- Keep API rate limits and demo reset protections enabled.
- Do not resize the instance, attach disks, enable backups, make the OSS bucket
  public, or add paid services.
- If any free quota becomes unclear or exhausted, stop the affected integration.
  The application can continue in deterministic mode without Qwen or OSS.

## Teardown

Release the ECS instance and delete the OSS bucket and its objects as soon as the
hackathon judging window ends, and in all cases before either trial expires.
Stopping an instance is not sufficient if its disk or other retained resources
can still accrue charges. After teardown, verify the billing console shows no
running resources and USD 0 actual charges.
