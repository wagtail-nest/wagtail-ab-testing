import React, { FunctionComponent, useEffect } from 'react';
import ReactDOM from 'react-dom';
import styled from 'styled-components';

// A label element without Wagtail's 'float: left;' rule applied
const SunkenLabel = styled.label`
    float: unset;
    width: unset;
`;

interface PageAPI {
    id: number;
    meta: {
        type: string;
    };
    title: string;
}

const GoalPageSelectorDiv = styled.div`
    padding-top: 20px;
`;

interface GoalPageSelectorProps {
    onChangeSelectedPage(pageInfo: PageAPI | null): void;
}

const GoalPageSelector: FunctionComponent<GoalPageSelectorProps> = ({
    onChangeSelectedPage,
}) => {
    const [selectedPageId, setSelectedPageId] = React.useState<number | null>(
        null,
    );
    const [selectedPageInfo, setSelectedPageInfo] =
        React.useState<PageAPI | null>(null);

    // Fetch info about the page whenever the selected page ID is changed
    useEffect(() => {
        if (selectedPageId) {
            fetch(
                `${wagtailConfig.ADMIN_ROOT_URL}api/main/pages/${selectedPageId}/`,
            )
                .then((response) => response.json())
                .then(setSelectedPageInfo);
        } else {
            setSelectedPageInfo(null);
        }
    }, [selectedPageId]);

    // When we fetch new page info, run a callback so the 'Goal event' select box can update
    useEffect(() => {
        onChangeSelectedPage(selectedPageInfo);
    }, [selectedPageInfo]);

    const onClickChooseDifferentPage = (
        e: React.MouseEvent<HTMLButtonElement>,
    ) => {
        e.preventDefault();
        (window as any).ModalWorkflow({
            url: (window as any).AB_TESTING_CHOOSE_PAGE_URL,
            onload: (window as any).PAGE_CHOOSER_MODAL_ONLOAD_HANDLERS,
            responses: {
                pageChosen: function (pageData: any) {
                    setSelectedPageId(pageData.id);
                },
            },
        });
    };

    const onClickClear = (e: React.MouseEvent<HTMLButtonElement>) => {
        e.preventDefault();
        setSelectedPageId(null);
    };

    return (
        <GoalPageSelectorDiv>
            {selectedPageInfo && (
                <p>
                    <b>{gettext('Selected page:')}</b> {selectedPageInfo.title}
                </p>
            )}
            <button
                className="button button-primary"
                onClick={onClickChooseDifferentPage}
            >
                {selectedPageInfo
                    ? gettext('Choose a different page')
                    : gettext('Choose a page')}
            </button>
            {selectedPageInfo && (
                <button
                    className="button button-primary"
                    onClick={onClickClear}
                >
                    {gettext('Clear')}
                </button>
            )}
            <input
                type="hidden"
                name="goal_page"
                value={selectedPageId || ''}
            />
        </GoalPageSelectorDiv>
    );
};

interface FieldProps {
    readonly visible?: boolean;
}

const Field = styled.div<FieldProps>`
    padding-top: 10px;
    padding-bottom: 10px;
    display: ${(props) => (props.visible != false ? 'block' : 'none')};
`;

const RequiredMark = () => <span className="w-required-mark">*</span>;

interface GoalSelectorProps {
    goalTypesByPageType: {
        [pageType: string]: {
            slug: string;
            name: string;
        }[];
    };
    globalGoalTypes: {
        slug: string;
        name: string;
    }[];
}

const GoalSelector: FunctionComponent<GoalSelectorProps> = ({
    goalTypesByPageType,
    globalGoalTypes,
}) => {
    const [selectedPageType, setSelectedPageType] = React.useState<
        string | null
    >(null);

    const onChangeSelectedPage = (pageInfo: PageAPI | null) => {
        if (pageInfo) {
            setSelectedPageType(pageInfo.meta.type);
        } else {
            setSelectedPageType(null);
        }
    };

    const goalTypes = selectedPageType
        ? goalTypesByPageType[selectedPageType.toLowerCase()] || []
        : globalGoalTypes;

    return (
        <div>
            <Field className="w-panel__wrapper">
                <SunkenLabel className="w-field__label">
                    {gettext('Which page is the goal on?')}
                </SunkenLabel>
                <GoalPageSelector onChangeSelectedPage={onChangeSelectedPage} />
            </Field>
            <Field visible={!!goalTypes} className="w-panel__wrapper">
                <SunkenLabel className="w-field__label">
                    {gettext('What is the goal?')}
                    <RequiredMark />
                </SunkenLabel>
                <div className="w-field__input">
                    <select name="goal_event">
                        <option key="" value="">
                            Choose a goal
                        </option>
                        {goalTypes.map(({ slug, name }) => (
                            <option key={slug} value={slug}>
                                {name}
                            </option>
                        ))}
                    </select>
                </div>
            </Field>
            <div className="w-panel__wrapper">
                <fieldset>
                    <div className="">
                        {gettext(
                            'By default pages only have one goal (Page Visit). Read the developer docs to learn why, and how to add custom goals.',
                        )}
                    </div>
                </fieldset>
            </div>
        </div>
    );
};

export function initGoalSelector() {
    const goalSelectorProps = JSON.parse(
        document.getElementById('data-goal-selector-props')?.textContent ||
            '{}',
    );

    document
        .querySelectorAll('div[data-component="goal-selector"]')
        .forEach((element: HTMLDivElement) => {
            element.setAttribute('data-props', goalSelectorProps);

            if (!element.dataset.props) {
                return;
            }

            ReactDOM.render(
                <GoalSelector {...JSON.parse(element.dataset.props)} />,
                element,
            );
        });
}
