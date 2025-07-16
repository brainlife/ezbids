import { Dcm2niix } from '@niivue/dcm2niix';
import anatYaml from '../bids-specification/src/schema/rules/datatypes/anat.yaml';
import funcYaml from '../bids-specification/src/schema/rules/datatypes/func.yaml';
import fmapYaml from '../bids-specification/src/schema/rules/datatypes/fmap.yaml';
import dwiYaml from '../bids-specification/src/schema/rules/datatypes/dwi.yaml';

export async function dcmToNii(files: File[]) {
    // dcm2niix --progress y -v 1 -ba n -z o -d 9 -f 'time-%t-sn-%s' $path
    const dcm2niix = new Dcm2niix();
    await dcm2niix.init();
    const convertedFiles = await dcm2niix.input(files).v(1).ba('n').z('o').d(9).f('time-%t-sn-%s').run();
    return convertedFiles;
}

export async function readTextFile(file: File): Promise<string> {
    return await new Promise((resolve) => {
        let fileReader = new FileReader();
        fileReader.onload = (e) => resolve(fileReader.result as string);
        fileReader.readAsText(file);
    });
}

export async function findMetadata(files: File[]) {
    const metadata = {} as any;

    for (const file of files) {
        if (file.name.endsWith('.json')) {
            const fileName = file.name.split('.').slice(0, -1).join('.');
            const content = await readTextFile(file);
            metadata[fileName] = JSON.parse(content);
        }
    }

    for (const key of Object.keys(metadata)) {
        const file = files.find((file) => file.name.startsWith(key + '.'));
        if (file) {
            metadata[key].file = file;
        }
    }

    return metadata;
}

const isIndexNumber = typeof index === 'number';
const regex = /(\.\d+)|(\d+(\.\d+)?)|([^\d.]+)|(\.(\D+|$))/g;

const parseItem = (item) => String(item).toLowerCase().match(regex);

function nSort(a, b) {
    if (a === b) return 0;

    const [aParts, bParts] = [a[0], b[0]];
    let i = 0;

    while (i < aParts.length) {
        if (!bParts[i]) return 1;

        const [aVal, bVal] = [aParts[i], bParts[i]];
        i++;

        if (aVal !== bVal) {
            const numComparison = aVal - bVal;
            if (!isNaN(numComparison)) return numComparison;
            return aVal > bVal ? 1 : -1;
        }
    }

    return bParts[i] !== undefined ? -1 : 0;
}

const accepted_datatypes = ['anat', 'dwi', 'fmap', 'func', 'perf', 'pet', 'meg'];
const MEG_extensions = ['.ds', '.fif', '.sqd', '.con', '.raw', '.ave', '.mrk', '.kdf', '.mhd', '.trg', '.chn', '.dat'];

function determineDirection(properPeDirection: string, ornt: string) {
    /**
     * Determines the "_dir-" entity label for BIDS based on phase encoding
     * direction and image orientation.
     *
     * @param {string} properPeDirection - Phase encoding direction in "ijk" format.
     * @param {string} ornt - Image orientation string (e.g., from nibabel's aff2axcodes).
     * @returns {string} - Direction for the BIDS "_dir-" entity label.
     */
    const axes = [
        ['R', 'L'],
        ['A', 'P'],
        ['S', 'I'],
    ];
    const axIdcs = { i: 0, j: 1, k: 2 };
    let axcode = ornt[axIdcs[properPeDirection[0]]];
    let inv = properPeDirection.slice(1) === '-';

    if (properPeDirection[0] === 'i' && axcode.includes('L')) {
        inv = !inv;
    } else if (properPeDirection[0] === 'j' && axcode.includes('P')) {
        inv = !inv;
    } else if (properPeDirection[0] === 'k' && axcode.includes('I')) {
        inv = !inv;
    }

    let direction = '';
    for (let ax of axes) {
        for (let flip of [ax, ax.slice().reverse()]) {
            if (flip[Number(!inv)].startsWith(axcode)) {
                direction = flip.join('');
            }
        }
    }

    return direction;
}

async function modifyUploadedDatasetList(fileList, uploadedImgList, dataDir, MEGExtensions = []) {
    let uploadedFilesList = [];
    uploadedImgList = uploadedImgList.sort(naturalSort);

    let config = false;
    let configFile = '';
    let excludeData = false;

    // Find ezBIDS configuration file
    let configFileList = [];
    // const walkDir = (dir) => {
    //     fs.readdirSync(dir, { withFileTypes: true }).forEach(file => {
    //         const fullPath = path.join(dir, file.name);
    //         if (file.isDirectory()) {
    //             walkDir(fullPath);
    //         } else if (file.name.endsWith('ezBIDS_template.json')) {
    //             configFileList.push(fullPath);
    //         }
    //     });
    // };
    // walkDir(dataDir);

    if (configFileList.length) {
        config = true;
        configFile = configFileList[configFileList.length - 1]; // Select the last (most recent) config file
    }

    // Parse image files
    for (const imgFile of uploadedImgList) {
        let ext;
        if (imgFile.endsWith('.nii.gz')) {
            ext = '.nii.gz';
        } else if (imgFile.endsWith('.v.gz')) {
            ext = '.v.gz';
        } else if (imgFile.endsWith('.ds')) {
            ext = '.ds';
        } else {
            ext = path.extname(imgFile);
        }

        // if (!MEGExtensions.some(ext => imgFile.endsWith(ext)) && !imgFile.endsWith('blood.json')) {
        //     try {
        //         const data = fs.readFileSync(imgFile);
        //         if (!nii.isNIFTI(data)) {
        //             throw new Error("Invalid NIfTI file");
        //         }
        //     } catch (error) {
        //         excludeData = true;
        //         console.log(`${imgFile} is not a properly formatted imaging file. Will not be converted by ezBIDS.`);
        //         break;
        //     }
        // }

        const imgDir = imgFile.name.split('/').slice(0, -1).join('/');
        let groupedFiles = fileList.filter((file) => path.basename(file).startsWith(path.basename(imgFile, ext) + '.'));

        // // Handle PET issue: remove blood-related files from non-blood data
        // if (!imgFile.includes("blood") && groupedFiles.some(f => f.includes("blood"))) {
        //     groupedFiles = groupedFiles.filter(f => !f.includes("blood"));
        // } else if (groupedFiles.some(f => f.endsWith('.v') || f.endsWith('.v.gz'))) {
        //     groupedFiles = groupedFiles.filter(f => !f.endsWith('.v') && !f.endsWith('.v.gz'));
        // }

        uploadedFilesList.push(groupedFiles);
    }

    // Flatten and sort uploadedFilesList
    uploadedFilesList = uploadedFilesList.flat().sort(naturalSort);

    return { uploadedFilesList, excludeData, config, configFile };
}

async function generateDatasetList(files: File[], excludedData: boolean) {
    let datasetList = [];

    // Get separate NIfTI and JSON (sidecar) lists
    let imgList = files
        .filter(
            (file) =>
                file.name.endsWith('nii.gz') ||
                file.name.endsWith('blood.json') ||
                MEG_extensions.some((ext) => file.name.endsWith(ext))
        )
        .sort((a, b) => nSort(a.name, b.name));

    let correspondingFilesList = files
        .filter(
            (file) =>
                file.name.endsWith('.json') ||
                file.name.endsWith('.bval') ||
                file.name.endsWith('.bvec') ||
                MEG_extensions.some((ext) => file.name.endsWith(ext)) ||
                file.name.endsWith('blood.tsv')
        )
        .sort((a, b) => nSort(a.name, b.name));

    console.log('\nDetermining unique acquisitions in dataset');
    console.log('------------------------------------------');

    let subInfoListId = '01';
    let subInfoList = [];

    for (let imgFile of imgList) {
        let ext = imgFile.name.endsWith('.nii.gz')
            ? '.nii.gz'
            : imgFile.name.endsWith('.v.gz')
            ? '.v.gz'
            : imgFile.name.endsWith('.ds')
            ? '.ds'
            : '.' + imgFile.name.split('.').pop();

        let correspondingJson = imgFile.name.endsWith('.blood.json')
            ? imgFile
            : correspondingFilesList.find(
                  (file) => file.name.endsWith('.json') && file.name.includes(imgFile.name.replace(ext, ''))
              );

        let jsonPath = correspondingJson || imgFile.name.replace(ext, '.json');
        let jsonData = {} as any;

        if (correspondingJson) {
            try {
                const text = await readTextFile(correspondingJson);
                jsonData = JSON.parse(text);
            } catch (err) {
                jsonData = { ConversionSoftware: 'ezBIDS', ConversionSoftwareVersion: '1.0.0' };
            }
        } else {
            jsonData = { ConversionSoftware: 'ezBIDS', ConversionSoftwareVersion: '1.0.0' };
        }

        let modality = jsonData.Modality || 'MR';
        let peDirection = jsonData.PhaseEncodingDirection || null;
        let ornt = 'RAS';

        let ped = peDirection ? determineDirection(peDirection, ornt) : '';

        let filesize = imgFile.size;

        let studyId = jsonData.StudyID || imgFile.name.split('/')[1];
        let patientId = jsonData.PatientID || 'n/a';
        let patientName = jsonData.PatientName || 'n/a';
        let patientBirthDate = jsonData.PatientBirthDate ? jsonData.PatientBirthDate.replace(/-/g, '') : '00000000';
        let patientSpecies = 'homo sapiens';
        let patientSex = jsonData.PatientSex || 'n/a';
        let patientAge = jsonData.PatientAge || 'n/a';
        let patientHandedness = 'n/a';

        let age = 'n/a';
        if (jsonData.PatientAge && typeof jsonData.PatientAge === 'number') {
            age = jsonData.PatientAge;
        }

        let acquisitionDateTime = jsonData.AcquisitionDateTime || '0000-00-00T00:00:00.000000';
        let acquisitionDate = jsonData.AcquisitionDate || '0000-00-00';
        let acquisitionTime = jsonData.AcquisitionTime || '00:00:00.000000';

        let manufacturer = jsonData.Manufacturer || 'n/a';

        let repetitionTime = jsonData.RepetitionTime || 0;
        let echoNumber = jsonData.EchoNumber || null;
        let echoTime = jsonData.EchoTime || 0;

        let volumeCount = 1;
        let ndim = 2;

        let seriesNumber = jsonData.SeriesNumber || 0;
        let modSeriesNumber = seriesNumber < 10 ? '0' + seriesNumber : seriesNumber.toString();

        let seriesDescription = jsonData.SeriesDescription || 'n/a';
        let descriptor = jsonData.SeriesDescription ? 'SeriesDescription' : 'ProtocolName';

        let protocolName = jsonData.ProtocolName || 'n/a';
        if (seriesDescription === 'n/a' && protocolName === 'n/a') {
            seriesDescription = imgFile;
        }

        let imageType = jsonData.ImageType || [];

        let dataType = excludedData ? 'excluded' : '';

        let folder = 'n/a';
        if (patientId === 'n/a' && patientName === 'n/a' && patientBirthDate === '00000000') {
            let parts = imgFile.name.split('/');
            folder = parts[parts.length - 2];
        }

        let subInfo = {
            PatientID: patientId,
            PatientName: patientName,
            PatientBirthDate: patientBirthDate,
            Folder: folder,
            Subject: subInfoListId,
        };
        subInfoList.push(subInfo);

        if (subInfoList.length > 1 && JSON.stringify(subInfo) !== JSON.stringify(subInfoList[subInfoList.length - 2])) {
            subInfoListId = (parseInt(subInfoListId, 10) + 1).toString().padStart(2, '0');
            subInfoList[subInfoList.length - 1].Subject = subInfoListId;
        }

        let subject = subInfo.Subject;
        let session = '';

        let subSearchTerm = 'sub-';
        let sesSearchTerm = 'ses-';

        for (let value of [imgFile.name, patientId, patientName]) {
            if (value.toLowerCase().includes(subSearchTerm)) {
                subject = value
                    .toLowerCase()
                    .split(subSearchTerm)[1]
                    .split(/[^a-zA-Z0-9]/)[0];
                break;
            }
        }

        for (let value of [imgFile.name, patientId, patientName]) {
            if (value.toLowerCase().includes(sesSearchTerm)) {
                session = value
                    .toLowerCase()
                    .split(sesSearchTerm)[1]
                    .split(/[^a-zA-Z0-9]/)[0];
                break;
            }
        }

        subject = subject.replace(/[^A-Za-z0-9]/g, '');
        session = session.replace(/[^A-Za-z0-9]/g, '');

        let correspondingFilePaths = correspondingFilesList.filter(
            (file) => file.name.includes(imgFile.name.replace(ext, '.')) && !file.name.endsWith(ext)
        );

        let paths = [...correspondingFilePaths.map((f) => f.name), imgFile.name].sort(nSort);

        let sequenceInfoDirectory = {
            StudyID: studyId,
            PatientID: patientId,
            PatientName: patientName,
            PatientBirthDate: patientBirthDate,
            PatientSpecies: patientSpecies,
            PatientSex: patientSex,
            PatientAge: age,
            PatientHandedness: patientHandedness,
            subject: subject,
            session: session,
            SeriesNumber: seriesNumber,
            ModifiedSeriesNumber: modSeriesNumber,
            AcquisitionDateTime: acquisitionDateTime,
            AcquisitionDate: acquisitionDate,
            AcquisitionTime: acquisitionTime,
            SeriesDescription: seriesDescription,
            ProtocolName: protocolName,
            descriptor: descriptor,
            Modality: modality,
            ImageType: imageType,
            RepetitionTime: repetitionTime,
            EchoNumber: echoNumber,
            EchoTime: echoTime,
            datatype: '',
            suffix: '',
            direction: ped,
            exclude: false,
            filesize: filesize,
            NumVolumes: volumeCount,
            orientation: ornt,
            error: null,
            type: dataType,
            nifti_path: imgFile,
            json_path: jsonPath,
            paths: paths,
            sidecar: jsonData,
        };

        datasetList.push(sequenceInfoDirectory);
    }

    console.log(datasetList);

    datasetList.sort(
        (a, b) =>
            nSort(a.AcquisitionDate, b.AcquisitionDate) || nSort(a.subject, b.subject) || nSort(a.session, b.session)
    );

    return datasetList;
}

function organizeDataset(datasetList: Object[]) {
    /**
     * Organizes data files into pseudo subject (and session, if applicable) groups.
     * This is particularly necessary when anonymized data is provided since crucial metadata
     * like AcquisitionDateTime, PatientID, and PatientName are removed.
     *
     * @param {Array} datasetList - List of objects containing metadata about the dataset.
     * @returns {Array} - Sorted and updated list with assigned pseudo-subjects.
     */

    datasetList.sort(
        (a, b) =>
            nSort(a.subject, b.subject) ||
            nSort(a.AcquisitionTime, b.AcquisitionTime) ||
            nSort(a.ModifiedSeriesNumber, b.ModifiedSeriesNumber)
    );

    let pseudoSub = 1;

    for (let index = 0; index < datasetList.length; index++) {
        let uniqueDic = datasetList[index];

        if (uniqueDic.subject === 'n/a') {
            if (
                uniqueDic.AcquisitionDateTime === '0000-00-00T00:00:00.000000' &&
                uniqueDic.PatientID === 'n/a' &&
                uniqueDic.PatientName === 'n/a'
            ) {
                let subj;

                if (index === 0) {
                    subj = pseudoSub;
                } else {
                    let previousData = datasetList[index - 1];

                    if (uniqueDic.SeriesNumber >= previousData.SeriesNumber) {
                        if (Math.abs(uniqueDic.SeriesNumber - previousData.SeriesNumber) >= 2) {
                            // Probably a misalignment, adjust pseudo subject ID
                            subj = pseudoSub - 1;
                        } else {
                            subj = pseudoSub;
                        }
                    } else {
                        if (parseInt(uniqueDic.SeriesNumber, 10) === 1) {
                            // Likely moving onto a new subject or session, increment pseudo subject ID
                            pseudoSub += 1;
                        }
                        subj = pseudoSub;
                    }
                }

                uniqueDic.subject = uniqueDic.subject + String(subj).padStart(4, '0');
                uniqueDic.AcquisitionDateTime = uniqueDic.subject.slice(0, -4);
            }
        }
    }

    datasetList.sort(
        (a, b) =>
            nSort(a.subject, b.subject) ||
            nSort(a.AcquisitionTime, b.AcquisitionTime) ||
            nSort(a.ModifiedSeriesNumber, b.ModifiedSeriesNumber)
    );

    return datasetList;
}

async function determineSubSesIDs(datasetList: Object[], bidsCompliant) {
    let dateCounter = 1;
    let subjectIdxCounter = 0;
    let subsInformation = [];
    let participantsInfo = {};

    // Determine unique subjects from uploaded dataset
    let uniqueSubjects = [...new Set(datasetList.map((x) => x.subject))];

    for (let sub of uniqueSubjects) {
        let subDicsList = datasetList.filter((x) => x.subject === sub);

        // Assign unique subject_idx values
        for (let x of subDicsList) {
            x.subject_idx = subjectIdxCounter;
        }
        subjectIdxCounter++;

        let participantsInfoData = [];
        if (bidsCompliant) {
            let bidsRootDir = fs.readFileSync(`${DATA_DIR}/bids_compliant.log`, 'utf8').split('\n')[0];

            if (fs.existsSync(`${bidsRootDir}/participants.tsv`)) {
                participantsInfoData = await parseTSV(`${bidsRootDir}/participants.tsv`);
                participantsInfo = {};

                let participantsInfoColumns = participantsInfoData.columns
                    .filter((col) => col !== 'participant_id')
                    .concat(['PatientID', 'PatientName']);

                participantsInfoData.data.forEach((row, lenIndex) => {
                    participantsInfo[lenIndex] = {};

                    for (let col of participantsInfoColumns) {
                        if (!['PatientID', 'PatientName'].includes(col)) {
                            participantsInfo[lenIndex][col] = String(row[col] || '');
                        } else {
                            let participantID = row['participant_id'].includes('sub-')
                                ? row['participant_id'].split('-').pop()
                                : row['participant_id'];
                            participantsInfo[lenIndex]['PatientID'] = participantID;
                            participantsInfo[lenIndex]['PatientName'] = participantID;
                        }
                    }
                });
            }
        } else {
            let phenotypeInfo = {
                species: subDicsList[0].PatientSpecies,
                sex: subDicsList[0].PatientSex,
                age: subDicsList[0].PatientAge,
                handedness: subDicsList[0].PatientHandedness,
                PatientName: subDicsList[0].PatientID,
                PatientID: subDicsList[0].PatientName,
                FileDirectory: subDicsList[0].file_directory,
            };
            participantsInfo[String(subDicsList[0].subject_idx)] = phenotypeInfo;
        }

        // Determine all unique sessions per subject
        let uniqueSesDateTimes = [];
        let sessionIdxCounter = 0;
        let sesDates = [...new Set(subDicsList.map((x) => [x.session, x.AcquisitionDate].join('|')))].map((x) =>
            x.split('|')
        );

        for (let sesDate of sesDates) {
            let acquisitionTimes = subDicsList
                .filter((x) => x.session === sesDate[0] && x.AcquisitionDate === sesDate[1])
                .map((x) => x.AcquisitionTime);

            let dic = {
                session: sesDate[0],
                AcquisitionDate: sesDate[1],
                AcquisitionTime: acquisitionTimes[0] || '00:00:00',
                exclude: false,
                session_idx: 0,
            };
            uniqueSesDateTimes.push(dic);
        }

        // Sorting method based on whether data is anonymized
        if (uniqueSesDateTimes[0].AcquisitionDate !== '0000-00-00') {
            uniqueSesDateTimes.sort(
                (a, b) =>
                    nSort(a.AcquisitionDate, b.AcquisitionDate) ||
                    nSort(a.AcquisitionTime, b.AcquisitionTime) ||
                    nSort(a.session, b.session)
            );
        } else {
            uniqueSesDateTimes.sort((a, b) => nSort(a.session, b.session));
        }

        // Assign unique session_idx values
        for (let dic of uniqueSesDateTimes) {
            dic.session_idx = sessionIdxCounter;
            sessionIdxCounter++;
        }

        // Pair patient information with session information
        let patientInfo = uniqueSesDateTimes.map((sesInfo) => ({
            PatientID:
                subDicsList.find((x) => x.session === sesInfo.session && x.AcquisitionDate === sesInfo.AcquisitionDate)
                    ?.PatientID || 'n/a',
            PatientName:
                subDicsList.find((x) => x.session === sesInfo.session && x.AcquisitionDate === sesInfo.AcquisitionDate)
                    ?.PatientName || 'n/a',
            PatientBirthDate:
                subDicsList.find((x) => x.session === sesInfo.session && x.AcquisitionDate === sesInfo.AcquisitionDate)
                    ?.PatientBirthDate || '00000000',
            file_directory:
                subDicsList.find((x) => x.session === sesInfo.session && x.AcquisitionDate === sesInfo.AcquisitionDate)
                    ?.file_directory || '',
        }));

        // Ensure uniqueness of AcquisitionDate
        let uniqueSesDates = uniqueSesDateTimes.map((x) => [x.session, x.AcquisitionDate]);
        for (let sesDate of uniqueSesDates) {
            let uniqueDatesDicsList = uniqueSesDateTimes.filter((x) => x.AcquisitionDate === sesDate[1]);
            if (uniqueDatesDicsList.length > 1) {
                for (let dateDic of uniqueDatesDicsList) {
                    dateDic.AcquisitionDate = `${sesDate[1]}.${dateCounter}`;
                    dateCounter++;
                }
            }
        }

        // Update dataset list with updated AcquisitionDate and session_idx info
        for (let subSesMapDic of uniqueSesDateTimes) {
            datasetList.forEach((dataDic) => {
                if (
                    dataDic.subject === sub &&
                    dataDic.session === subSesMapDic.session &&
                    dataDic.AcquisitionDate === subSesMapDic.AcquisitionDate.split('.')[0]
                ) {
                    dataDic.AcquisitionDate = subSesMapDic.AcquisitionDate;
                    dataDic.session_idx = subSesMapDic.session_idx;
                }
            });
        }

        // Construct subject/session information in ezBIDS-compatible format
        let subjectIDsInfo = {
            subject: sub,
            PatientInfo: patientInfo,
            phenotype: {
                species: subDicsList[0].PatientSpecies,
                sex: subDicsList[0].PatientSex,
                age: subDicsList[0].PatientAge,
                handedness: subDicsList[0].PatientHandedness,
            },
            exclude: false,
            sessions: uniqueSesDateTimes.map(({ session_idx, AcquisitionTime, ...rest }) => rest),
            validationErrors: [],
        };

        subsInformation.push(subjectIDsInfo);
    }

    return { datasetList, subsInformation, participantsInfo };
}

/**
 * Helper function to parse TSV files.
 *
 * @param {string} filePath - Path to the TSV file.
 * @returns {Promise<Object>} - Parsed TSV data with columns and data array.
 */
function parseTSV(filePath) {
    return new Promise((resolve, reject) => {
        let results = [];
        let columns = [];
        let isFirstRow = true;

        fs.createReadStream(filePath)
            .pipe(csv({ separator: '\t' }))
            .on('headers', (headers) => {
                columns = headers;
            })
            .on('data', (data) => {
                results.push(data);
            })
            .on('end', () => {
                resolve({ columns, data: results });
            })
            .on('error', (err) => {
                reject(err);
            });
    });
}

/**
 * Groups individual acquisitions into unique series based on DICOM metadata.
 * Unique series are determined using SeriesDescription, EchoTime, ImageType, and RepetitionTime.
 *
 * @param {Array} datasetList - List of objects containing metadata about the dataset.
 * @param {boolean} bidsCompliant - True if uploaded data is already BIDS-compliant.
 * @returns {Object} - Contains the updated dataset list and a list of unique series.
 */
function determineUniqueSeries(datasetList, bidsCompliant) {
    let datasetListUniqueSeries = [];
    let seriesChecker = [];
    let seriesIdx = 0;

    datasetList.forEach((acquisitionDic, index) => {
        let descriptor = acquisitionDic.descriptor;

        let heuristicItems = [
            Math.round(acquisitionDic.EchoTime * 10) / 10,
            acquisitionDic.SeriesDescription.includes('_RR')
                ? acquisitionDic[descriptor].replace('_RR', '')
                : acquisitionDic[descriptor],
            acquisitionDic.ImageType,
            Math.round(acquisitionDic.RepetitionTime * 10) / 10,
        ];

        if (bidsCompliant) {
            acquisitionDic.series_idx = index === 0 ? 0 : seriesIdx++;
            datasetListUniqueSeries.push(acquisitionDic);
        } else {
            if (index === 0) {
                acquisitionDic.series_idx = 0;
                datasetListUniqueSeries.push(acquisitionDic);
            } else {
                let seriesSubset = seriesChecker.map((x) => x.slice(1, 3));
                let fullSeriesSet = seriesChecker.map((x) => x.slice(0, -1));

                if (!seriesSubset.some((item) => JSON.stringify(item) === JSON.stringify(heuristicItems.slice(1, 3)))) {
                    seriesIdx++;
                    acquisitionDic.series_idx = seriesIdx;
                    datasetListUniqueSeries.push(acquisitionDic);
                } else if (!fullSeriesSet.some((item) => JSON.stringify(item) === JSON.stringify(heuristicItems))) {
                    seriesIdx++;
                    acquisitionDic.series_idx = seriesIdx;
                    datasetListUniqueSeries.push(acquisitionDic);
                } else {
                    let commonSeriesIndex = fullSeriesSet.findIndex(
                        (item) => JSON.stringify(item) === JSON.stringify(heuristicItems)
                    );
                    let commonSeriesIdx = seriesChecker[commonSeriesIndex][seriesChecker[commonSeriesIndex].length - 1];
                    acquisitionDic.series_idx = commonSeriesIdx;
                }
            }

            seriesChecker.push([...heuristicItems, acquisitionDic.series_idx]);
        }
    });

    return { datasetList, datasetListUniqueSeries };
}

function generateDatasetDescription() {
    // DATA_DIR, bidsCompliant
    let datasetDescriptionDic = {};

    // if (bidsCompliant) {
    //     const logFilePath = path.join(DATA_DIR, 'bids_compliant.log');

    //     try {
    //         const bidsRootDir = fs.readFileSync(logFilePath, 'utf8').split('\n')[0].trim();
    //         const datasetDescriptionPath = path.join(bidsRootDir, 'dataset_description.json');

    //         if (fs.existsSync(datasetDescriptionPath)) {
    //             const datasetDescription = JSON.parse(fs.readFileSync(datasetDescriptionPath, 'utf8'));

    //             for (const field in datasetDescription) {
    //                 if (!(field in datasetDescriptionDic) && !field.includes("GeneratedBy")) {
    //                     datasetDescriptionDic[field] = datasetDescription[field];
    //                 }
    //             }
    //         }
    //     } catch (error) {
    //         console.error("Error reading BIDS dataset description:", error);
    //     }
    // } else {
    //     const datasetDescriptionYaml = require('./dataset_description.yaml'); // Assuming this file exists
    //     datasetDescriptionDic = datasetDescriptionYaml["dataset_description"]["fields"].reduce((acc, field) => {
    //         if (!field.includes("GeneratedBy")) acc[field] = "";
    //         return acc;
    //     }, {});
    //     datasetDescriptionDic["SourceDatasets"] = [];
    // }

    datasetDescriptionDic['GeneratedBy'] = [
        {
            Name: 'ezBIDS',
            Version: '1.0.0',
            Description:
                'ezBIDS is a web-based tool for converting neuroimaging datasets to BIDS, requiring neither coding nor knowledge of the BIDS specification',
            CodeURL: 'https://brainlife.io/ezbids/',
            Container: {
                Type: 'docker',
                Tag: 'brainlife/ezbids-handler',
            },
        },
    ];

    // Ensure required fields have default values
    datasetDescriptionDic['Name'] = datasetDescriptionDic['Name'] || 'Untitled';
    datasetDescriptionDic['BIDSVersion'] = datasetDescriptionDic['BIDSVersion'] || '1.9.0';
    datasetDescriptionDic['DatasetType'] = datasetDescriptionDic['DatasetType'] || 'raw';

    return datasetDescriptionDic;
}

function generateParticipantsColumns() {
    // DATA_DIR, bidsCompliant
    /**
     * Generates column information for the participants.json file.
     *
     * @param {string} DATA_DIR - Root-level directory where uploaded data is stored.
     * @param {boolean} bidsCompliant - True if data is BIDS-compliant, otherwise false.
     * @returns {Object} - Column information for the participants.json file.
     */

    let participantsColumnInfo = {};

    participantsColumnInfo = {
        sex: {
            Description: 'Sex of the participant(s)',
            Levels: {
                M: 'male',
                F: 'female',
                O: 'other',
            },
        },
        age: {
            Description: 'Age of the participant(s)',
            Units: 'year',
        },
    };

    // const logFilePath = path.join(DATA_DIR, 'bids_compliant.log');

    // try {
    //     const bidsRootDir = fs.readFileSync(logFilePath, 'utf8').split('\n')[0].trim();
    //     const participantsJsonPath = path.join(bidsRootDir, 'participants.json');

    //     if (bidsCompliant && fs.existsSync(participantsJsonPath)) {
    //         participantsColumnInfo = JSON.parse(fs.readFileSync(participantsJsonPath, 'utf8'));
    //     } else {
    //         participantsColumnInfo = {
    //             sex: {
    //                 Description: "Sex of the participant(s)",
    //                 Levels: {
    //                     M: "male",
    //                     F: "female",
    //                     O: "other"
    //                 }
    //             },
    //             age: {
    //                 Description: "Age of the participant(s)",
    //                 Units: "year"
    //             }
    //         };
    //     }
    // } catch (error) {
    //     console.error("Error processing participants.json:", error);
    // }

    return participantsColumnInfo;
}

function createLookupInfo() {
    /**
     * Creates a lookup dictionary for identifying different
     * datatypes, suffixes, and entity label information.
     *
     * @returns {Object} - Lookup dictionary with conditions for various datatypes.
     */

    let lookupDic = {};

    // Add localizers to lookupDic
    lookupDic['localizer'] = {
        exclude: {
            search_terms: ['localizer', 'scout'],
            accepted_entities: [],
            required_entities: [],
            conditions: ['"_i0000" in uniqueDic["paths"][0]'],
        },
    };

    // Load datatypes.yaml
    const datatypesYaml = {
        anat: {
            name: 'Anatomical Magnetic Resonance Imaging',
            description: 'Magnetic resonance imaging sequences designed to characterize static, anatomical features.\n',
        },
        beh: {
            name: 'Behavioral Data',
            description: 'Behavioral data.\n',
        },
        dwi: {
            name: 'Diffusion-Weighted Imaging',
            description: 'Diffusion-weighted imaging (DWI).\n',
        },
        eeg: {
            name: 'Electroencephalography',
            description: 'Electroencephalography',
        },
        fmap: {
            name: 'Field maps',
            description: 'MRI scans for estimating B0 inhomogeneity-induced distortions.\n',
        },
        func: {
            name: 'Task-Based Magnetic Resonance Imaging',
            description: 'Task (including resting state) imaging data\n',
        },
        ieeg: {
            name: 'Intracranial electroencephalography',
            description: 'Intracranial electroencephalography (iEEG) or electrocorticography (ECoG) data\n',
        },
        meg: {
            name: 'Magnetoencephalography',
            description: 'Magnetoencephalography',
        },
        micr: {
            name: 'Microscopy',
            description: 'Microscopy',
        },
        perf: {
            name: 'Perfusion imaging',
            description: 'Blood perfusion imaging data, including arterial spin labeling (ASL)\n',
        },
        pet: {
            name: 'Positron Emission Tomography',
            description: 'Positron emission tomography data\n',
        },
    };

    const acceptedDatatypes = Object.keys(datatypesYaml); // Assuming accepted datatypes are defined in YAML

    acceptedDatatypes.forEach((datatype) => {
        if (!datatypesYaml[datatype]) return;

        lookupDic[datatype] = {};

        // const rulePath = path.join(__dirname, 'datatype_suffix_rules', `${datatype}.yaml`);
        // const rule = yaml.load(fs.readFileSync(rulePath, 'utf8'));

        let rule;
        switch (datatype) {
            case 'anat':
                rule = anatYaml;
                break;
            case 'func':
                rule = funcYaml;
                break;
            case 'fmap':
                rule = fmapYaml;
                break;
            case 'dwi':
                rule = dwiYaml;
                break;
        }

        if (!rule) return lookupDic;

        Object.keys(rule).forEach((key) => {
            let suffixes = rule[key]['suffixes'];

            // Remove or filter suffixes based on datatype-specific rules
            switch (datatype) {
                case 'anat':
                    suffixes = suffixes.filter((x) => !['T2star', 'FLASH', 'PD'].includes(x));
                    break;
                case 'dwi':
                    suffixes = suffixes.filter((x) => ['dwi', 'sbref'].includes(x));
                    break;
                case 'fmap':
                    suffixes = suffixes.filter((x) => !['m0scan'].includes(x));
                    break;
                case 'func':
                    suffixes = suffixes.filter((x) => !['events', 'stim', 'physio', 'phase'].includes(x));
                    break;
                case 'perf':
                    suffixes = suffixes.filter((x) => !['aslcontext', 'asllabeling', 'physio', 'stim'].includes(x));
                    break;
                case 'pet':
                    suffixes = suffixes.filter((x) => ['pet', 'blood'].includes(x));
                    break;
                case 'meg':
                    suffixes = suffixes.filter((x) => x === 'meg' && key === 'meg');
                    break;
            }

            suffixes.forEach((suffix) => {
                lookupDic[datatype][suffix] = {
                    search_terms: [suffix.toLowerCase()],
                    accepted_entities: [],
                    required_entities: [],
                    conditions: [],
                };

                if (rule[key]['suffixes'].includes(suffix)) {
                    const entities = rule[key]['entities'];

                    lookupDic[datatype][suffix]['accepted_entities'] = Object.keys(entities).filter(
                        (x) => !['subject', 'session'].includes(x)
                    );

                    lookupDic[datatype][suffix]['required_entities'] = Object.keys(entities).filter(
                        (x) => !['subject', 'session'].includes(x) && entities[x] === 'required'
                    );

                    // Additional datatype-specific rules
                    if (datatype === 'anat') {
                        lookupDic[datatype][suffix]['conditions'].push('uniqueDic["ndim"] == 3');

                        if (suffix === 'T1w') {
                            lookupDic[datatype][suffix]['search_terms'].push(
                                'tfl3d',
                                'tfl_3d',
                                'mprage',
                                'mp_rage',
                                'spgr',
                                'tflmgh',
                                'tfl_mgh',
                                't1mpr',
                                't1_mpr',
                                'anatt1',
                                'anat_t1',
                                '3dt1',
                                '3d_t1'
                            );
                            lookupDic[datatype][suffix]['conditions'].push(
                                '"inv1" not in sd && "inv2" not in sd && "uni_images" not in sd'
                            );
                        } else if (suffix === 'T2w') {
                            lookupDic[datatype][suffix]['search_terms'].push(
                                'anatt2',
                                'anat_t2',
                                '3dt2',
                                '3d_t2',
                                't2spc',
                                't2_spc'
                            );
                            lookupDic[datatype][suffix]['conditions'].push('uniqueDic["EchoTime"] > 100');
                        } else if (suffix === 'FLAIR') {
                            lookupDic[datatype][suffix]['search_terms'].push(
                                't2spacedafl',
                                't2_space_da_fl',
                                't2space_da_fl',
                                't2space_dafl',
                                't2_space_dafl'
                            );
                        } else if (suffix === 'T2starw') {
                            lookupDic[datatype][suffix]['search_terms'].push('qsm');
                            lookupDic[datatype][suffix]['conditions'].push('"EchoNumber" not in uniqueDic["sidecar"]');
                        }
                    } else if (datatype === 'func') {
                        if (['bold', 'sbref'].includes(suffix)) {
                            lookupDic[datatype][suffix]['search_terms'].push(
                                'func',
                                'bold',
                                'fmri',
                                'fcmri',
                                'fcfmri',
                                'rsfmri',
                                'rsmri',
                                'task',
                                'rest'
                            );
                            if (suffix === 'bold') {
                                lookupDic[datatype][suffix]['conditions'].push(
                                    'uniqueDic["ndim"] == 4',
                                    'uniqueDic["NumVolumes"] > 1',
                                    'uniqueDic["RepetitionTime"] > 0',
                                    '!("DERIVED" in uniqueDic["ImageType"] || "PERFUSION" in uniqueDic["ImageType"])'
                                );
                            } else if (suffix === 'sbref') {
                                lookupDic[datatype][suffix]['conditions'].push(
                                    '"DIFFUSION" not in uniqueDic["ImageType"]',
                                    '"sbref" in sd && uniqueDic["NumVolumes"] == 1',
                                    'uniqueDic["ndim"] == 3'
                                );
                            }
                        }
                    } else if (datatype === 'dwi') {
                        if (['dwi', 'sbref'].includes(suffix)) {
                            lookupDic[datatype][suffix]['search_terms'].push('dwi', 'dti', 'dmri');
                            if (suffix === 'dwi') {
                                lookupDic[datatype][suffix]['conditions'].push(
                                    'any(".bvec" in x for x in uniqueDic["paths"])',
                                    'uniqueDic["NumVolumes"] > 1'
                                );
                            }
                        }
                    }
                }
            });
        });
    });

    // Add DWI derivatives (TRACEW, FA, ADC) to lookup dictionary
    lookupDic['dwi_derivatives'] = {
        exclude: {
            search_terms: ['trace', '_fa_', 'adc'],
            accepted_entities: [],
            required_entities: [],
            conditions: ['"DIFFUSION" in uniqueDic["ImageType"]'],
        },
    };

    return lookupDic;
}

function datatypeSuffixIdentification(datasetListUniqueSeries, lookupDic, config) {
    /**
     * Identifies datatype and suffix for each unique acquisition in the dataset.
     *
     * @param {Array} datasetListUniqueSeries - List of acquisitions with a unique series group ID.
     * @param {Object} lookupDic - Dictionary of datatype and suffix rules.
     * @param {boolean} config - True if an ezBIDS configuration file was detected.
     * @returns {Array} - Updated dataset list with identified datatype and suffix.
     */

    console.log('\nDatatype & suffix identification');
    console.log('------------------------------------');

    datasetListUniqueSeries.forEach((uniqueDic, index) => {
        const jsonPath = uniqueDic['json_path'];

        if (uniqueDic['type'] === 'exclude' && !uniqueDic['finalized_match']) {
            uniqueDic['error'] =
                'Uploaded imaging data file contains an improper format ' +
                'which cannot be read by ezBIDS. Cannot convert file.';
            uniqueDic['message'] = uniqueDic['error'];
        } else if (!uniqueDic['finalized_match']) {
            // Check JSON paths for explicit datatype and suffix information
            for (const datatype of Object.keys(lookupDic)) {
                if (jsonPath.name.includes(`/${datatype}/`)) {
                    uniqueDic['datatype'] = datatype;
                }

                // const rulePath = path.join(__dirname, 'datatype_suffix_rules', `${datatype}.yaml`);
                // const rule = yaml.load(fs.readFileSync(rulePath, 'utf8'));

                // let suffixes = Object.values(rule).flatMap((r) => r['suffixes']);
                // const shortSuffixes = suffixes.filter((x) => x.length < 3);
                const shortSuffixes = [];

                const unhelpfulSuffixes = [
                    'fieldmap',
                    'beh',
                    'epi',
                    'magnitude',
                    'magnitude1',
                    'magnitude2',
                    'phasediff',
                ];

                const badSuffixes = [...shortSuffixes, ...unhelpfulSuffixes];
                const deprecatedSuffixes = ['T2star', 'FLASH', 'PD', 'phase'];
                // suffixes = suffixes.filter((x) => !deprecatedSuffixes.includes(x));

                // for (const suffix of suffixes) {
                //     if (jsonPath.includes(`_${suffix}.json`)) {
                //         uniqueDic['suffix'] = suffix;
                //     }
                // }

                for (const badSuffix of badSuffixes) {
                    if (jsonPath.name.includes(`_${badSuffix}.json`)) {
                        uniqueDic['datatype'] = badSuffix === 'fieldmap' ? 'fmap' : badSuffix;
                        uniqueDic['suffix'] = badSuffix;
                    }
                }

                // Correct BIDS deprecation issue: func/phase -> func/bold
                if (uniqueDic['datatype'] === 'func' && uniqueDic['suffix'] === 'phase') {
                    uniqueDic['suffix'] = 'bold';
                }

                if (uniqueDic['datatype'] && uniqueDic['suffix']) {
                    uniqueDic['message'] =
                        `Acquisition is believed to be ${uniqueDic['datatype']}/${uniqueDic['suffix']} ` +
                        `because '${uniqueDic['suffix']}' is in the file path. Please modify if incorrect.`;
                }
            }
        }

        // If file ends in blood.json, assign datatype/suffix
        // if (jsonPath.endsWith('blood.json')) {
        //     uniqueDic['datatype'] = 'pet';
        //     uniqueDic['suffix'] = 'blood';
        //     uniqueDic['type'] = 'pet/blood';
        //     uniqueDic['message'] =
        //         'Acquisition is believed to be pet/blood ' +
        //         "because the file path ends with '_blood.json'. Please modify if incorrect.";
        // }

        // Further checks using dcm2niix's BidsGuess heuristic
        if (!uniqueDic['finalized_match'] && (!uniqueDic['datatype'] || !uniqueDic['suffix']) && !uniqueDic['type']) {
            const jsonData = uniqueDic['sidecar'];

            if (jsonData['BidsGuess']) {
                const bidsGuess = jsonData['BidsGuess'];
                if (bidsGuess.length === 2) {
                    let datatype = bidsGuess[0].toLowerCase();
                    let suffix = bidsGuess[1].split('_').pop();

                    for (const bidsRefSuffix of Object.keys(lookupDic)) {
                        if (bidsRefSuffix.toLowerCase() === suffix.toLowerCase()) {
                            suffix = bidsRefSuffix;
                        }
                    }

                    if (suffix === 'bold' && uniqueDic['NumVolumes'] === 1) {
                        const sd =
                            uniqueDic[uniqueDic['descriptor']].replace(/[^A-Za-z0-9]+/g, '_').toLowerCase() + '_';
                        if (sd.includes('sbref')) {
                            suffix = 'sbref';
                        }
                    }

                    if (!Object.keys(lookupDic).includes(datatype)) {
                        uniqueDic['message'] =
                            `Acquisition was determined to be a non-BIDS sequence ` +
                            `according to dcm2niix's BidsGuess heuristic. Please modify if incorrect.`;
                        uniqueDic['type'] = 'exclude';
                    } else {
                        uniqueDic['datatype'] = datatype;
                        uniqueDic['suffix'] = suffix;
                        uniqueDic['message'] =
                            `Acquisition is believed to be ${datatype}/${suffix} ` +
                            `based on the dcm2niix BidsGuess heuristic. Please modify if incorrect.`;
                    }
                }
            }

            // Additional search term checks
            if ((!uniqueDic['datatype'] || !uniqueDic['suffix']) && uniqueDic['type'] !== 'exclude') {
                const descriptor = uniqueDic['descriptor'];
                const sd = uniqueDic[descriptor].replace(/[^A-Za-z0-9]+/g, '_').toLowerCase() + '_';

                for (const datatype of Object.keys(lookupDic)) {
                    if (!['localizer', 'dwi_derivatives'].includes(datatype)) {
                        for (const suffix of Object.keys(lookupDic[datatype])) {
                            const searchTerms = lookupDic[datatype][suffix]['search_terms'];
                            const conditions = lookupDic[datatype][suffix]['conditions'];

                            if (searchTerms.some((term) => sd.includes(term))) {
                                uniqueDic['datatype'] = datatype;
                                uniqueDic['suffix'] = suffix;
                                uniqueDic['message'] =
                                    `Acquisition is believed to be ${datatype}/${suffix} ` +
                                    `because '${searchTerms.find((term) =>
                                        sd.includes(term)
                                    )}' is in the ${descriptor}. ` +
                                    'Please modify if incorrect.';
                                break;
                            }
                        }
                    }
                }
            }
        }

        // Assign type variable for brainlife.io storage
        if (!uniqueDic['finalized_match'] && !uniqueDic['type'].includes('exclude')) {
            uniqueDic['type'] = `${uniqueDic['datatype']}/${uniqueDic['suffix']}`;
        }

        // Additional warnings for anatomical scans
        if (
            !uniqueDic['finalized_match'] &&
            uniqueDic['datatype'] === 'anat' &&
            !uniqueDic['ImageType'].includes('NORM')
        ) {
            uniqueDic['message'] +=
                ' Additionally, this acquisition appears to be non-normalized, potentially having poor CNR. ' +
                'If a normalized version exists, consider excluding this one.';
        }
    });

    // Exclude individual echoes if mean RMS anatomical file exists
    if (!config) {
        const anatMERMS = datasetListUniqueSeries.filter(
            (v) => v['datatype'] === 'anat' && v['ImageType'].includes('MEAN')
        );

        anatMERMS.forEach((rmsFile) => {
            const descriptor = rmsFile['descriptor'];
            datasetListUniqueSeries.forEach((acquisition) => {
                if (acquisition['descriptor'].replace(/[^A-Za-z0-9]+/g, '') === descriptor.replace('RMS', '')) {
                    acquisition['message'] =
                        ' A mean RMS anatomical file was found, so this individual echo file will be excluded. ' +
                        'Please modify if incorrect.';
                    acquisition['type'] = 'exclude';
                }
            });
        });
    }

    return datasetListUniqueSeries;
}

function entityLabelsIdentification(datasetListUniqueSeries, lookupDic) {
    /**
     * Identifies acquisition entity labels (e.g., dir-, echo-) based on metadata
     * and sorts them according to BIDS specification ordering.
     *
     * @param {Array} datasetListUniqueSeries - List of acquisitions with a unique series group ID.
     * @param {Object} lookupDic - Dictionary with datatype and suffix rules.
     * @returns {Array} - Updated dataset list with identified entity labels.
     */

    console.log('\nEntity label identification');
    console.log('----------------------------');

    // const entityOrderingPath = path.join(__dirname, 'entity_ordering.yaml');
    // const entityOrdering = yaml.load(fs.readFileSync(entityOrderingPath, 'utf8'));

    let tb1afiTr = 1;
    let tb1srgeTd = 1;

    datasetListUniqueSeries.forEach((uniqueDic) => {
        if (!uniqueDic['finalized_match']) {
            let seriesEntities = {};
            const descriptor = uniqueDic['descriptor'];
            const regex = /[^\w.]/g; // Matches non-alphanumeric characters except for "."
            const sd = uniqueDic[descriptor].replace(regex, '_').toLowerCase() + '_';
            const jsonPath = uniqueDic['json_path'];

            // Check if entity labels follow BIDS naming conventions
            for (const key in lookupDic) {
                if (!['subject', 'session', 'direction'].includes(key)) {
                    const entity = lookupDic[key]['entity'];
                    if (sd.includes(`_${entity}_`)) {
                        seriesEntities[key] = sd
                            .split(`${entity}_`)
                            .pop()
                            .split(/[^a-zA-Z0-9]/)[0];
                    } else if (jsonPath.name.includes(`_${entity}-`)) {
                        seriesEntities[key] = jsonPath
                            .split(`${entity}-`)
                            .pop()
                            .split(/[^a-zA-Z0-9]/)[0];
                    } else {
                        seriesEntities[key] = '';
                    }
                } else {
                    seriesEntities[key] = '';
                }

                // Remove placeholder task entity label for MEG data
                if (key === 'task' && seriesEntities['task'] === 'unknown') {
                    seriesEntities['task'] = '';
                }
            }

            // Identify task label
            const funcRestKeys = ['rest', 'rsfmri', 'fcmri', 'resting'];
            if (funcRestKeys.some((term) => sd.split('_').includes(term)) && !seriesEntities['task']) {
                seriesEntities['task'] = 'rest';
            }

            if (
                ['noise', 'emptyroom'].some((term) => sd.replace(regex, '').toLowerCase().includes(term)) ||
                seriesEntities['subject'] === 'emptyroom'
            ) {
                seriesEntities['task'] = 'noise';
            }

            // Direction entity for fmap/epi and dwi/dwi
            if (['fmap/epi', 'dwi/dwi'].some((type) => uniqueDic['type'].includes(type))) {
                seriesEntities['direction'] = uniqueDic['direction'];
            }

            // Echo entity
            if (
                uniqueDic['EchoNumber'] &&
                ![
                    'fmap/epi',
                    'fmap/magnitude1',
                    'fmap/magnitude2',
                    'fmap/phasediff',
                    'fmap/phase1',
                    'fmap/phase2',
                    'fmap/fieldmap',
                ].some((type) => uniqueDic['type'].includes(type))
            ) {
                seriesEntities['echo'] = String(uniqueDic['EchoNumber']);
            }

            // Flip entity
            if (
                ['anat/VFA', 'anat/MPM', 'anat/MTS', 'fmap/TB1EPI', 'fmap/TB1DAM'].some((type) =>
                    uniqueDic['type'].includes(type)
                ) &&
                'FlipAngle' in uniqueDic['sidecar']
            ) {
                const flipMatch = sd.match(/flip([1-9]*)/);
                seriesEntities['flip'] = flipMatch ? flipMatch[1] : '';
            }

            // Acquisition (acq) entity
            if (['fmap/TB1TFL', 'fmap/TB1RFM'].some((type) => uniqueDic['type'].includes(type))) {
                seriesEntities['acquisition'] = uniqueDic['ImageType'].includes('FLIP ANGLE MAP') ? 'fmap' : 'anat';
            }

            if (uniqueDic['type'].includes('fmap/TB1AFI')) {
                seriesEntities['acquisition'] = 'tr' + tb1afiTr++;
            }

            if (uniqueDic['type'].includes('fmap/TB1SRGE') && 'DelayTime' in uniqueDic['sidecar']) {
                seriesEntities['acquisition'] = 'td' + tb1srgeTd++;
            }

            if (uniqueDic['type'].includes('fmap/RB1COR') && 'ReceiveCoilName' in uniqueDic['sidecar']) {
                if (uniqueDic['sidecar']['ReceiveCoilName'].includes('Head')) {
                    seriesEntities['acquisition'] = 'head';
                } else if (uniqueDic['sidecar']['ReceiveCoilName'].includes('Body')) {
                    seriesEntities['acquisition'] = 'body';
                }
            }

            // MEG-specific acquisition labels
            if (['Elekta', 'Neuromag', 'MEGIN'].includes(uniqueDic['sidecar']['Manufacturer'])) {
                const sds = datasetListUniqueSeries.map((item) => item['SeriesDescription']);
                if (sds.some((desc) => desc.endsWith('.fif')) && sds.some((desc) => desc.endsWith('.dat'))) {
                    seriesEntities['acquisition'] = uniqueDic['SeriesDescription'].endsWith('.dat')
                        ? 'calibration'
                        : 'crosstalk';
                }
            }

            // Inversion entity
            if (
                ['anat/MP2RAGE', 'anat/IRT1'].some((type) => uniqueDic['type'].includes(type)) &&
                'InversionTime' in uniqueDic['sidecar']
            ) {
                const invMatch = sd.match(/inv([1-9]*)/);
                seriesEntities['inversion'] = invMatch ? invMatch[1] : '';
            }

            // Part entity
            if (uniqueDic['ImageType'].includes('REAL')) {
                seriesEntities['part'] = 'real';
            } else if (uniqueDic['ImageType'].includes('IMAGINARY')) {
                seriesEntities['part'] = 'imag';
            } else if (!uniqueDic['type'].includes('fmap') && uniqueDic['ImageType'].includes('PHASE')) {
                seriesEntities['part'] = 'phase';
            }

            // Reconstruction entity
            if (seriesEntities['reconstruction'] === 'pointspreadfunctionmodellingtimeofflight') {
                seriesEntities['reconstruction'] = 'PSTOF';
            }

            // Ensure only allowed entities exist for the datatype/suffix pair
            if (uniqueDic['type'] !== 'exclude') {
                const { datatype, suffix } = uniqueDic;
                const exposedEntities = Object.keys(seriesEntities).filter((key) => seriesEntities[key] !== '');

                exposedEntities.forEach((entity) => {
                    const acceptedEntities = lookupDic[datatype]?.[suffix]?.['accepted_entities'] || [];
                    if (!acceptedEntities.includes(entity)) {
                        if (!(datatype === 'anat' && entity === 'echo')) {
                            seriesEntities[entity] = '';
                        }
                    }
                });
            }

            // Clean up entity values
            for (const key in seriesEntities) {
                if (seriesEntities[key].includes('.')) {
                    seriesEntities[key] = seriesEntities[key].replace('.', 'p');
                } else if (!/^[A-Za-z0-9]+$/.test(seriesEntities[key])) {
                    seriesEntities[key] = seriesEntities[key].replace(regex, '');
                }
            }

            // Sort entities according to BIDS specification ordering
            // seriesEntities = Object.fromEntries(
            //     Object.entries(seriesEntities).sort(
            //         (a, b) => entityOrdering.indexOf(a[0]) - entityOrdering.indexOf(b[0])
            //     )
            // );

            uniqueDic['entities'] = seriesEntities;
        }
    });

    return datasetListUniqueSeries;
}

function updateDatasetList(datasetList, datasetListUniqueSeries) {
    /**
     * Updates datasetList with information from datasetListUniqueSeries using the series_idx identifier.
     *
     * @param {Array} datasetList - List of dictionaries containing metadata from JSON files.
     * @param {Array} datasetListUniqueSeries - List containing unique acquisitions with series group ID.
     * @returns {Array} - Updated datasetList with additional entity and type information.
     */

    datasetList.forEach((data) => {
        const uniqueDic = datasetListUniqueSeries.find((unique) => unique.series_idx === data.series_idx);
        if (uniqueDic) {
            data.entities = uniqueDic.entities;
            data.type = uniqueDic.type;
            data.error = uniqueDic.error;
            data.message = uniqueDic.message;
            data.IntendedFor = uniqueDic.IntendedFor;
            data.B0FieldIdentifier = uniqueDic.B0FieldIdentifier;
            data.B0FieldSource = uniqueDic.B0FieldSource;
        }
    });

    return datasetList;
}

function modifyObjectsInfo(datasetList) {
    /**
     * Updates dataset list with object-level information, section ID values,
     * image screenshots, and removes identifying metadata.
     *
     * @param {Array} datasetList - List of dictionaries containing metadata.
     * @returns {Array} - List of dictionaries with object-level information.
     */

    console.log('\nModifying Objects Information');
    console.log('------------------------------');

    // const entityOrderingPath = path.join(__dirname, 'entity_ordering.yaml');
    // const entityOrdering = yaml.load(fs.readFileSync(entityOrderingPath, 'utf8'));

    // Find unique subject/session index pairs and sort them
    const subjSesPairs = datasetList.map((x) => [x['subject_idx'], x['session_idx']]);
    const uniqueSubjSesPairs = [...new Set(subjSesPairs.map(JSON.stringify))].map(JSON.parse).sort();

    let objectsList = [];

    console.log('subjSesPairs', subjSesPairs);
    console.log('uniqueSubjSesPairs', uniqueSubjSesPairs);

    for (const uniqueSubjSes of uniqueSubjSesPairs) {
        const scanProtocol = datasetList.filter(
            (x) => x['subject_idx'] === uniqueSubjSes[0] && x['session_idx'] === uniqueSubjSes[1]
        );

        let objectsData = [];

        for (const protocol of scanProtocol) {
            if (protocol['nibabel_image'] === 'n/a') {
                protocol['headers'] = 'n/a';
            } else {
                const image = protocol['nibabel_image'];
                // protocol['headers'] = image.header.toString().split('\n').slice(1);

                // const objectImgArray = image.dataobj;
                // if (!['<i2', '<u2', '<f4', 'int16', 'uint16'].includes(objectImgArray.dtype)) {
                //     protocol['exclude'] = true;
                //     protocol['error'] =
                //         'The data array for this acquisition is improper, ' +
                //         "suggesting that this isn't an imaging file or is a non-BIDS specified acquisition " +
                //         'and will not be converted. Please modify if incorrect.';
                //     protocol['message'] = protocol['error'];
                //     protocol['type'] = 'exclude';
                // }

                // // Check for negative dimensions and exclude from BIDS conversion
                // if (image.shape.some((dim) => dim < 0)) {
                //     protocol['exclude'] = true;
                //     protocol['type'] = 'exclude';
                //     protocol['error'] = 'Image contains negative dimension(s) and cannot be converted to BIDS format';
                //     protocol['message'] = protocol['error'];
                // }
            }

            protocol['error'] = protocol['error'] ? [protocol['error']] : [];

            let objectsEntities = {};
            // Object.fromEntries(Object.keys(entityOrdering).map((key) => [key, '']));

            // Re-order entities to match BIDS specification
            // objectsEntities = Object.fromEntries(
            //     Object.entries(objectsEntities).sort(
            //         ([a], [b]) => entityOrdering.indexOf(a) - entityOrdering.indexOf(b)
            //     )
            // );

            let items = [];

            for (const item of protocol['paths']) {
                if (item.endsWith('.bval')) {
                    items.push({ path: item, name: 'bval' });
                } else if (item.endsWith('.bvec')) {
                    items.push({ path: item, name: 'bvec' });
                } else if (item.endsWith('.json')) {
                    items.push({ path: item, name: 'json', sidecar: protocol['sidecar'] });

                    // if (item.endsWith('blood.json')) {
                    //     const tsvPath = item.replace('.json', '.tsv');
                    //     try {
                    //         const headers = await readTSVHeaders(tsvPath);
                    //         items.push({ path: tsvPath, name: 'tsv', headers });
                    //     } catch (error) {
                    //         console.error(`Error reading TSV file: ${tsvPath}`, error);
                    //     }
                    // }
                } else if (item.endsWith('.nii.gz')) {
                    items.push({ path: item, name: 'nii.gz', pngPaths: [], headers: protocol['headers'] });
                } else if (MEG_extensions.some((ext) => item.endsWith(ext))) {
                    let name = item.endsWith('.ds') ? '.ds' : path.extname(item);
                    items.push({ path: item, name, pngPaths: [], headers: protocol['headers'] });
                }
            }

            let objectsInfo = {
                subject_idx: protocol['subject_idx'],
                session_idx: protocol['session_idx'],
                series_idx: protocol['series_idx'],
                message: protocol['message'],
                AcquisitionDate: protocol['AcquisitionDate'],
                AcquisitionTime: protocol['AcquisitionTime'],
                SeriesNumber: protocol['SeriesNumber'],
                ModifiedSeriesNumber: protocol['ModifiedSeriesNumber'],
                IntendedFor: protocol['IntendedFor'],
                B0FieldIdentifier: protocol['B0FieldIdentifier'],
                B0FieldSource: protocol['B0FieldSource'],
                entities: objectsEntities,
                items: items,
                PED: protocol['direction'],
                analysisResults: {
                    NumVolumes: protocol['NumVolumes'],
                    errors: protocol['error'],
                    warnings: [],
                    filesize: protocol['filesize'],
                    orientation: protocol['orientation'],
                    section_id: 1,
                },
            };

            objectsData.push(objectsInfo);
        }

        objectsList.push(objectsData);
    }

    // Flatten list of lists
    objectsList = objectsList.flat();

    return objectsList;
}

function extractSeriesInfo(datasetListUniqueSeries) {
    /**
     * Extracts a subset of acquisition information for display on the
     * Series-level page of the ezBIDS UI.
     *
     * @param {Array} datasetListUniqueSeries - List of dictionaries containing unique series acquisitions.
     * @returns {Array} - List of dictionaries containing subset of acquisition information.
     */

    return datasetListUniqueSeries.map((uniqueDic) => ({
        SeriesDescription: uniqueDic['SeriesDescription'],
        EchoTime: uniqueDic['EchoTime'],
        ImageType: uniqueDic['ImageType'],
        RepetitionTime: uniqueDic['RepetitionTime'],
        NumVolumes: uniqueDic['NumVolumes'],
        IntendedFor: uniqueDic['IntendedFor'],
        B0FieldIdentifier: uniqueDic['B0FieldIdentifier'],
        B0FieldSource: uniqueDic['B0FieldSource'],
        nifti_path: uniqueDic['nifti_path'],
        series_idx: uniqueDic['series_idx'],
        AcquisitionDateTime: uniqueDic['AcquisitionDateTime'],
        PED: uniqueDic['direction'],
        entities: uniqueDic['entities'],
        type: uniqueDic['type'],
        error: uniqueDic['error'],
        message: uniqueDic['message'],
        object_indices: [],
    }));
}

export async function preprocess(files: File[]) {
    let datasets = await generateDatasetList(files, false);
    datasets = organizeDataset(datasets);

    let { datasetList, subsInformation, participantsInfo } = await determineSubSesIDs(datasets, false);
    let { datasetListUniqueSeries } = determineUniqueSeries(datasetList, false);

    const readme = `
This data was converted using ezBIDS (https://brainlife.io/ezbids).
Additional information regarding this dataset can be entered in this file.
`;

    const dataset_description_dic = generateDatasetDescription();
    const participants_column_info = generateParticipantsColumns();
    const events = {
        columnKeys: null,
        columns: {
            onsetLogic: 'eq',
            onset: null,
            onset2: null,
            onsetUnit: 'sec',
            durationLogic: 'eq',
            duration: null,
            duration2: null,
            durationUnit: 'sec',
            sampleLogic: 'eq',
            sample: null,
            sample2: null,
            sampleUnit: 'samples',
            trialType: null,
            responseTimeLogic: 'eq',
            responseTime: null,
            responseTime2: null,
            responseTimeUnit: 'sec',
            values: null,
            HED: null,
            stim_file: null,
        },
        loaded: false,
        sampleValues: {},
        trialTypes: {
            desc: 'Indicator of type of action that is expected',
            levels: {},
            longName: 'Event category',
        },
    };

    const lookupDic = createLookupInfo();

    const config = {};

    datasetListUniqueSeries = datatypeSuffixIdentification(datasetListUniqueSeries, lookupDic, config);
    // datasetListUniqueSeries = check_dwi_b0maps(datasetListUniqueSeries)
    datasetListUniqueSeries = entityLabelsIdentification(datasetListUniqueSeries, lookupDic);
    // datasetListUniqueSeries = check_part_entity(datasetListUniqueSeries, config)
    // datasetListUniqueSeries = set_IntendedFor_B0FieldIdentifier_B0FieldSource(datasetListUniqueSeries, bids_compliant)

    datasetList = updateDatasetList(datasetList, datasetListUniqueSeries);
    const objects_list = modifyObjectsInfo(datasetList);

    const ui_series_info_list = extractSeriesInfo(datasetListUniqueSeries);

    const EZBIDS = {
        readme: readme,
        datasetDescription: dataset_description_dic,
        subjects: subsInformation,
        participantsColumn: participants_column_info,
        participantsInfo: participantsInfo,
        series: ui_series_info_list,
        objects: objects_list,
        events: events,
        BIDSURI: false,
    };

    return EZBIDS;
}
