# RDNA2(gfx1030)에서 Strata 돌리기: RX 6900 XT 한 장 + 램 64GB 레시피

[English](README.md)

이 저장소는 [Strata](https://github.com/Niko1221/Strata)로 Qwen3.8-Flash-Next를 **AMD Radeon RX 6900 XT 16GB 한 장**과 **램 64GB** 리눅스(ROCm) 기계에서 돌리면서 맞춘 설정, 패치, 측정값을 모은 것이다. Strata 문서는 RX 6000 패키지를 "실제 카드로 시험하지 않음"으로 적고 RX 6000 사용자의 보고를 요청하고 있다. 이 저장소는 그 보고 중 하나다.

**이 기계의 결과:** 처음 읽는 9.7K~119K 프롬프트의 프리필 약 1,200~1,300 tok/s, 짧은 후속 요청의 디코드 50~64 tok/s, 컨텍스트 256K, 이미지 입력 켬. 같은 기계의 시작점은 프리필 382~414 tok/s(9.7K), 디코드 26~37 tok/s였다.

| | |
|---|---|
| [`hardware.md`](hardware.md) | 기계 사양, ROCm, 엔진 빌드 옵션 |
| [`results/`](results/README.md) | 바꾼 것마다의 측정 효과, VRAM 분해, 실제 요청 분포 |
| [`rejected.md`](rejected.md) | 이 하드웨어에서 시도했다가 손해 본 것 |
| [`config/engine.example.json`](config/engine.example.json) | 경로를 자리표시자로 바꾼 서버 설정 |
| [`patches/`](patches/README.md) | Strata v0.1.42용 엔진 패치 5개(그중 3개는 본가 PR 백포트)와 서버 패치 |

## 빠른 시작

1. gfx103x를 아는 ROCm을 준비한다. 이 기계는 AMD TheRock `gfx103X-all` 10.0.0 tarball을 사용자 폴더에 풀어 썼고, `HSA_OVERRIDE_GFX_VERSION`은 쓰지 않았다.
2. Strata `v0.1.42`를 받아 `patches/engine/*.patch`를 적용한다. Python 서버를 쓰면 `patches/serve/*.diff`도 적용한다. 빌드 옵션은 `hardware.md`에 있다.
3. ISTA-DASLab SC117 IQ3_XXS 파일을 받아 Strata 도구로 전문가 pack을 만든다. 이 저장소에는 모델 파일이 없다.
4. `config/engine.example.json`을 복사해 `<...>` 경로를 채우고 서버를 켠다.

## 효과가 컸던 순서

1. **IQ3_S 대신 IQ3_XXS.** 램 64GB에서는 40GiB인 IQ3_XXS 전문가가 페이지 캐시에 다 올라가고, 47GiB인 IQ3_S는 다 못 올라간다. 이것만으로 프리필이 1.1~3.5배 올랐고 디코드는 22~41에서 40~45 tok/s가 됐다.
2. **gfx1030 프롬프트 경로:** rocBLAS 튜닝표를 쓴 FP16 프롬프트 GEMM(`STRATA_HIP_PROMPT_F16`, `STRATA_ROCBLAS_TUNING`), SIMT QSA select. #3381 프롬프트 어텐션 백포트(패치 0005)는 int8 KV에서만 돈다. 최종 설정의 k8v4 KV에서는 split 경로로 되돌아가 아무 일도 하지 않는다(`results/` 3단계).
3. **GDN 스위치**(`STRATA_GDN_HEAD/PP/CONVL2/NOY`, `STRATA_CVEC_FUSE`): 프롬프트 길이에 따라 +5~12%.
4. **`STRATA_ROUTE_RESIDENT=1.0`:** 디코드 +8~18%. 다만 모델 출력이 달라진다. 자기 작업으로 품질을 확인할 것.
5. **램은 페이지 캐시에 양보한다.** 전문가를 램에 고정하거나 상주 KV를 늘리면 전부 느려졌다.

## 한계

- 기계 하나, 모델 하나. 칸마다 실행 횟수가 적다(대부분 2~4회).
- 엔진 기반은 v0.1.42다. 본가는 그 뒤로 많이 바뀌었다(작성 시점 v0.2.8). 일부는 이미 본가에 들어갔거나 더는 맞지 않을 수 있다.
- IQ3_XXS, k8v4, 256K 설정에서 답변 품질은 끝까지 측정하지 않았다.

## 라이선스

MIT. 패치는 Strata(MIT, Niko1221 and the Strata contributors)에서 파생됐다. 패치 0002, 0003, 0005는 @Vop3p가 올린 Strata PR #1151, #1167, #3381을 백포트한 것이고, 그 변경의 공로는 원작자에게 있다.
